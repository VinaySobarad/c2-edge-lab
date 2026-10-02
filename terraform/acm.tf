resource "aws_acm_certificate" "edge" {
  count = local.use_custom_domain ? 1 : 0

  provider          = aws.us_east_1
  domain_name       = var.domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "acm_validation" {
  for_each = {
    for option in flatten([
      for cert in aws_acm_certificate.edge : cert.domain_validation_options
      ]) : option.domain_name => {
      name   = option.resource_record_name
      record = option.resource_record_value
      type   = option.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = var.hosted_zone_id
}

resource "aws_acm_certificate_validation" "edge" {
  count = local.use_custom_domain ? 1 : 0

  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.edge[0].arn
  validation_record_fqdns = [for record in aws_route53_record.acm_validation : record.fqdn]
}
