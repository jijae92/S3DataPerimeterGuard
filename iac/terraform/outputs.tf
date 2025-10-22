output "bucket_arn" {
  description = "ARN of the protected S3 bucket"
  value       = aws_s3_bucket.data_perimeter.arn
}
