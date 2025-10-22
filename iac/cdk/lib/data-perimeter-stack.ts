import { join, resolve } from 'path';
import { mkdtempSync, readFileSync } from 'fs';
import { tmpdir } from 'os';
import { execFileSync } from 'child_process';
import { CfnJson, CfnOutput, Fn, Stack, StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { aws_s3 as s3, aws_ssm as ssm } from 'aws-cdk-lib';

interface PlaceholderContext {
  readonly bucketArn: string;
  readonly bucketName: string;
  readonly orgId: string;
  readonly vpcEndpointId: string;
}

export interface DataPerimeterStackProps extends StackProps {
  readonly bucketName: string;
  readonly orgId: string;
  readonly vpcEndpointId: string;
  /** Optional path to override baseline policy location (defaults to repo ./policies/bucket-policy.base.json). */
  readonly basePolicyPath?: string;
  /** Optional path to override exceptions catalogue (defaults to repo ./policies/bucket-policy.exceptions.json). */
  readonly exceptionsPath?: string;
  /** When true, persist the OrgId value to SSM Parameter Store. */
  readonly createOrgIdParameter?: boolean;
  /** Parameter Store name, required if createOrgIdParameter is true. */
  readonly orgIdParameterPath?: string;
}

export class DataPerimeterStack extends Stack {
  constructor(scope: Construct, id: string, props: DataPerimeterStackProps) {
    super(scope, id, props);

    const bucket = new s3.Bucket(this, 'DataPerimeterBucket', {
      bucketName: props.bucketName,
      objectOwnership: s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      versioned: true,
      autoDeleteObjects: false,
    });

    const mergedPolicy = this.mergePolicies(props, bucket);

    const policyJson = new CfnJson(this, 'MergedBucketPolicyJson', {
      value: mergedPolicy,
    });

    new s3.CfnBucketPolicy(this, 'DataPerimeterBucketPolicy', {
      bucket: bucket.bucketName,
      policyDocument: policyJson,
    });

    new CfnOutput(this, 'BucketName', {
      value: bucket.bucketName,
      description: 'Protected data perimeter bucket name',
    });

    new CfnOutput(this, 'BucketArn', {
      value: bucket.bucketArn,
      description: 'Protected data perimeter bucket ARN',
    });

    if (props.createOrgIdParameter) {
      if (!props.orgIdParameterPath) {
        throw new Error('orgIdParameterPath must be provided when createOrgIdParameter is true.');
      }

      new ssm.StringParameter(this, 'OrgIdParameter', {
        parameterName: props.orgIdParameterPath,
        stringValue: props.orgId,
        description: 'OrgId recorded for audit of data perimeter configuration',
      });
    }
  }

  private mergePolicies(props: DataPerimeterStackProps, bucket: s3.Bucket): Record<string, unknown> {
    const repoRoot = resolve(__dirname, '..', '..', '..');
    const basePolicyPath = props.basePolicyPath ?? join(repoRoot, 'policies', 'bucket-policy.base.json');
    const exceptionsPath = props.exceptionsPath ?? join(repoRoot, 'policies', 'bucket-policy.exceptions.json');
    const mergeScriptPath = join(repoRoot, 'tools', 'merge_policy.py');

    const tmpDir = mkdtempSync(join(tmpdir(), 'merged-policy-'));
    const outputPath = join(tmpDir, 'bucket-policy.merged.json');

    const pythonExecutable = this.resolvePythonExecutable();

    const args = [
      mergeScriptPath,
      '--base',
      basePolicyPath,
      '--exceptions',
      exceptionsPath,
      '--output',
      outputPath,
      '--json',
    ];

    try {
      execFileSync(pythonExecutable, args, {
        stdio: ['ignore', 'pipe', 'pipe'],
        cwd: repoRoot,
      });
    } catch (error) {
      throw new Error(`Failed to merge bucket policy using ${pythonExecutable}: ${error}`);
    }

    const mergedRaw = readFileSync(outputPath, 'utf-8');
    const mergedPolicy = JSON.parse(mergedRaw) as Record<string, unknown>;

    return this.replacePlaceholders(mergedPolicy, {
      bucketArn: bucket.bucketArn,
      bucketName: props.bucketName,
      orgId: props.orgId,
      vpcEndpointId: props.vpcEndpointId,
    }) as Record<string, unknown>;
  }

  private replacePlaceholders(value: unknown, context: PlaceholderContext): unknown {
    if (Array.isArray(value)) {
      return value.map((item) => this.replacePlaceholders(item, context));
    }

    if (value && typeof value === 'object') {
      const entries = Object.entries(value as Record<string, unknown>).map(([key, val]) => [
        key,
        this.replacePlaceholders(val, context),
      ] as const);
      return Object.fromEntries(entries);
    }

    if (typeof value !== 'string') {
      return value;
    }

    return this.substituteString(value, context);
  }

  private substituteString(value: string, context: PlaceholderContext): unknown {
    let result = value
      .replace(/\$\{BucketName}/g, context.bucketName)
      .replace(/\$\{OrgId}/g, context.orgId)
      .replace(/\$\{VpcEndpointId}/g, context.vpcEndpointId);

    if (!result.includes('${BucketArn}')) {
      return result;
    }

    if (result === '${BucketArn}') {
      return context.bucketArn;
    }

    const segments = result.split('${BucketArn}');
    const parts: string[] = [];
    segments.forEach((segment, index) => {
      if (segment) {
        parts.push(segment);
      }
      if (index < segments.length - 1) {
        parts.push(context.bucketArn);
      }
    });

    if (parts.length === 1) {
      return parts[0];
    }

    return Fn.join('', parts);
  }

  private resolvePythonExecutable(): string {
    const candidates = [process.env.CDK_PYTHON ?? '', 'python3', 'python'];
    for (const candidate of candidates) {
      if (!candidate) {
        continue;
      }
      try {
        execFileSync(candidate, ['--version'], { stdio: 'ignore' });
        return candidate;
      } catch (_) {
        // Continue searching.
      }
    }
    throw new Error('No Python interpreter found. Set CDK_PYTHON environment variable to a valid executable.');
  }
}
