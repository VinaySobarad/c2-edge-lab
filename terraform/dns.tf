resource "aws_route53_record" "edge_ipv4" {
  count = local.use_custom_domain ? 1 : 0

  zone_id = var.hosted_zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.edge.domain_name
    zone_id                = aws_cloudfront_distribution.edge.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "edge_ipv6" {
  count = local.use_custom_domain ? 1 : 0

  zone_id = var.hosted_zone_id
  name    = var.domain_name
  type    = "AAAA"

  alias {
    name                   = aws_cloudfront_distribution.edge.domain_name
    zone_id                = aws_cloudfront_distribution.edge.hosted_zone_id
    evaluate_target_health = false
  }
}
