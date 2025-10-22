#!/usr/bin/env node
import 'source-map-support/register';
import { App } from 'aws-cdk-lib';
import { DataPerimeterStack } from '../lib/data-perimeter-stack';

type MaybeString = string | undefined;

const app = new App();

const context = (key: string): MaybeString => {
  const value = app.node.tryGetContext(key);
  return typeof value === 'string' ? value : undefined;
};

const envValue = (key: string): MaybeString => process.env[key];

const bucketName = context('bucketName') ?? envValue('BUCKET_NAME') ?? 'example-data-perimeter-bucket';
const orgId = context('orgId') ?? envValue('ORG_ID') ?? 'o-exampleorg';
const vpcEndpointId = context('vpcEndpointId') ?? envValue('VPC_ENDPOINT_ID') ?? 'vpce-00000000000000000';
const createOrgParameterRaw = context('createOrgIdParameter') ?? envValue('CREATE_ORG_ID_PARAMETER');
const createOrgIdParameter = createOrgParameterRaw ? createOrgParameterRaw.toLowerCase() === 'true' : false;
const orgIdParameterPath = context('orgIdParameterPath') ?? envValue('ORG_ID_PARAMETER_PATH');

new DataPerimeterStack(app, 'S3DataPerimeterStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
  bucketName,
  orgId,
  vpcEndpointId,
  createOrgIdParameter,
  orgIdParameterPath,
});
