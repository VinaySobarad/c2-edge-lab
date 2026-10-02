provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

# CloudFront custom-domain certificates must live in var.acm_region (us-east-1).
provider "aws" {
  alias  = "us_east_1"
  region = var.acm_region

  default_tags {
    tags = local.common_tags
  }
}
