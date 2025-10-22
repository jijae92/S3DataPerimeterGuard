// Terraform stub providing functionality equivalent to the CDK stack. Optional alternative deployment path.
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }
}

locals {
  merged_policy_path = "${path.module}/../../build/bucket-policy.merged.json"
  bucket_arn         = format("arn:aws:s3:::%s", var.bucket_name)

  merged_policy = replace(
    replace(
      replace(
        replace(file(local.merged_policy_path), "${BucketArn}", local.bucket_arn),
        "${BucketName}", var.bucket_name
      ),
      "${OrgId}", var.org_id
    ),
    "${VpcEndpointId}", var.vpc_endpoint_id
  )
}

resource "aws_s3_bucket" "data_perimeter" {
  bucket = var.bucket_name
  force_destroy = false
}

resource "aws_s3_bucket_public_access_block" "data_perimeter" {
  bucket = aws_s3_bucket.data_perimeter.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "data_perimeter" {
  bucket = aws_s3_bucket.data_perimeter.id
  policy = local.merged_policy
}

output "bucket_name" {
  description = "Protected data perimeter bucket name"
  value       = aws_s3_bucket.data_perimeter.bucket
}
