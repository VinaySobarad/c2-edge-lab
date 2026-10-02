resource "random_id" "decoy_bucket" {
  byte_length = 4
}

resource "aws_s3_bucket" "decoy" {
  bucket        = "${var.name_prefix}-decoy-${random_id.decoy_bucket.hex}"
  force_destroy = var.decoy_force_destroy
}

resource "aws_s3_bucket_ownership_controls" "decoy" {
  bucket = aws_s3_bucket.decoy.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "decoy" {
  bucket = aws_s3_bucket.decoy.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "decoy" {
  bucket = aws_s3_bucket.decoy.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "decoy" {
  bucket = aws_s3_bucket.decoy.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_cloudfront_origin_access_control" "decoy" {
  name                              = "${var.name_prefix}-decoy-${random_id.decoy_bucket.hex}"
  description                       = "c2-edge-lab: CloudFront reads the private decoy bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

data "aws_iam_policy_document" "decoy" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.decoy.arn,
      "${aws_s3_bucket.decoy.arn}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  statement {
    sid    = "AllowCloudFrontReadViaOAC"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    actions = ["s3:GetObject"]
    resources = [
      for key in keys(local.decoy_objects) : "${aws_s3_bucket.decoy.arn}/${key}"
    ]

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values = [
        aws_cloudfront_distribution.edge.arn,
        aws_cloudfront_distribution.longhaul.arn,
      ]
    }
  }

  statement {
    sid    = "DenyCloudFrontStage"
    effect = "Deny"

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.decoy.arn}/${local.stage_key_prefix}/*"]
  }
}

resource "aws_s3_bucket_policy" "decoy" {
  bucket = aws_s3_bucket.decoy.id

  depends_on = [
    aws_s3_bucket_public_access_block.decoy,
    aws_s3_bucket_ownership_controls.decoy,
  ]

  policy = data.aws_iam_policy_document.decoy.json
}

resource "aws_s3_object" "decoy" {
  for_each = local.decoy_objects

  bucket        = aws_s3_bucket.decoy.id
  key           = each.key
  source        = "${local.decoy_root}/${each.key}"
  etag          = filemd5("${local.decoy_root}/${each.key}")
  content_type  = each.value
  cache_control = each.key == "index.html" ? "public, max-age=300" : "public, max-age=86400"

  depends_on = [
    aws_s3_bucket_server_side_encryption_configuration.decoy,
    aws_s3_bucket_versioning.decoy,
  ]
}

resource "aws_s3_bucket_lifecycle_configuration" "decoy" {
  bucket = aws_s3_bucket.decoy.id

  depends_on = [aws_s3_bucket_versioning.decoy]

  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  rule {
    id     = "expire-staged-binaries"
    status = "Enabled"

    filter {
      prefix = "${local.stage_key_prefix}/"
    }

    expiration {
      days = 7
    }
  }
}
