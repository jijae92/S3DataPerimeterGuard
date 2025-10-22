variable "bucket_name" {
  description = "Name of the S3 bucket to protect"
  type        = string
}

variable "org_id" {
  description = "AWS Organizations ID that should retain access"
  type        = string
}

variable "vpc_endpoint_id" {
  description = "VPC endpoint ID permitted to access the bucket"
  type        = string
}
