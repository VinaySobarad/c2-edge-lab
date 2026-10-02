# Look up AWS-managed policies by name. Hardcoded UUIDs are easy to mix up
# (CORS-CustomOrigin has been pasted as AllViewer in this repo once already).
# https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/cloudfront_cache_policy
# https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-managed-origin-request-policies.html

data "aws_cloudfront_cache_policy" "caching_optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_cache_policy" "caching_disabled" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_origin_request_policy" "all_viewer" {
  name = "Managed-AllViewer"
}

data "aws_cloudfront_response_headers_policy" "security_headers" {
  name = "Managed-SecurityHeadersPolicy"
}

# Short-haul public hostname. Identity burn keeps this dxxxx; hostname burn replaces it.
resource "aws_cloudfront_distribution" "edge" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "c2-edge-lab short-haul: S3 decoy + nginx ${join(" ", var.callback_path_patterns)}"
  default_root_object = "index.html"
  price_class         = var.cloudfront_price_class
  aliases             = local.use_custom_domain ? [var.domain_name] : []
  http_version        = "http2and3"
  wait_for_deployment = true

  origin {
    domain_name              = aws_s3_bucket.decoy.bucket_regional_domain_name
    origin_id                = local.decoy_origin_id
    origin_access_control_id = aws_cloudfront_origin_access_control.decoy.id
  }

  # Origin is the EIP's AWS reverse-DNS (CloudFront will not take a raw IP).
  # Identity burn replaces the EIP; this hostname follows it. Do not use
  # instance.public_dns — that value in state is from boot, before EIP association.
  origin {
    domain_name = local.redirector_origin_hostname
    origin_id   = local.redirector_origin_id

    custom_origin_config {
      http_port                = 80
      https_port               = 443
      origin_protocol_policy   = "http-only"
      origin_ssl_protocols     = ["TLSv1.2"]
      origin_read_timeout      = 60
      origin_keepalive_timeout = 5
    }
  }

  default_cache_behavior {
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    target_origin_id           = local.decoy_origin_id
    viewer_protocol_policy     = "redirect-to-https"
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.caching_optimized.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security_headers.id
  }

  dynamic "ordered_cache_behavior" {
    for_each = var.callback_path_patterns
    content {
      path_pattern             = ordered_cache_behavior.value
      allowed_methods          = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
      cached_methods           = ["GET", "HEAD"]
      target_origin_id         = local.redirector_origin_id
      viewer_protocol_policy   = "redirect-to-https"
      compress                 = false
      cache_policy_id          = data.aws_cloudfront_cache_policy.caching_disabled.id
      origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer.id
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = local.use_custom_domain ? false : true
    acm_certificate_arn            = local.use_custom_domain ? aws_acm_certificate_validation.edge[0].certificate_arn : null
    ssl_support_method             = local.use_custom_domain ? "sni-only" : null
    minimum_protocol_version       = local.use_custom_domain ? var.cloudfront_minimum_protocol_version : null
  }

  depends_on = [
    aws_s3_bucket_public_access_block.decoy,
    aws_s3_bucket_ownership_controls.decoy,
    aws_eip_association.redirector,
  ]
}

# Second public hostname (long-haul). Same origins; different dxxxx.cloudfront.net.
# Blocking the short-haul URL does not kill this distribution.
resource "aws_cloudfront_distribution" "longhaul" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "c2-edge-lab long-haul: S3 decoy + nginx ${join(" ", var.longhaul_path_patterns)}"
  default_root_object = "index.html"
  price_class         = var.cloudfront_price_class
  http_version        = "http2and3"
  wait_for_deployment = true

  origin {
    domain_name              = aws_s3_bucket.decoy.bucket_regional_domain_name
    origin_id                = local.decoy_origin_id
    origin_access_control_id = aws_cloudfront_origin_access_control.decoy.id
  }

  origin {
    domain_name = local.redirector_origin_hostname
    origin_id   = local.redirector_origin_id

    custom_origin_config {
      http_port                = 80
      https_port               = 443
      origin_protocol_policy   = "http-only"
      origin_ssl_protocols     = ["TLSv1.2"]
      origin_read_timeout      = 60
      origin_keepalive_timeout = 5
    }
  }

  default_cache_behavior {
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    target_origin_id           = local.decoy_origin_id
    viewer_protocol_policy     = "redirect-to-https"
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.caching_optimized.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security_headers.id
  }

  dynamic "ordered_cache_behavior" {
    for_each = var.longhaul_path_patterns
    content {
      path_pattern             = ordered_cache_behavior.value
      allowed_methods          = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
      cached_methods           = ["GET", "HEAD"]
      target_origin_id         = local.redirector_origin_id
      viewer_protocol_policy   = "redirect-to-https"
      compress                 = false
      cache_policy_id          = data.aws_cloudfront_cache_policy.caching_disabled.id
      origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer.id
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  depends_on = [
    aws_s3_bucket_public_access_block.decoy,
    aws_s3_bucket_ownership_controls.decoy,
    aws_eip_association.redirector,
  ]
}
