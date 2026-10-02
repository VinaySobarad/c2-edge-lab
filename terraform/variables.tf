variable "aws_region" {
  type        = string
  description = "Region for VPC, EC2, S3. ACM for CloudFront is acm_region (must stay us-east-1)."
  default     = "us-east-1"
}

variable "acm_region" {
  type        = string
  description = "ACM region for the CloudFront alias certificate. AWS requires us-east-1."
  default     = "us-east-1"

  validation {
    condition     = var.acm_region == "us-east-1"
    error_message = "CloudFront custom-domain certificates must be issued in us-east-1."
  }
}

variable "domain_name" {
  type        = string
  description = "Optional FQDN for a CloudFront alias. Empty uses the default dxxxx.cloudfront.net hostname (no ACM, no Route 53)."
  default     = ""

  validation {
    condition = var.domain_name == "" || can(regex(
      "^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$",
      var.domain_name,
    ))
    error_message = "domain_name must be empty or a DNS name such as lab.example.com, not a URL."
  }
}

variable "hosted_zone_id" {
  type        = string
  description = "Route 53 zone that owns domain_name. Required when domain_name is set; must be empty when it is not."
  default     = ""

  validation {
    condition     = var.hosted_zone_id == "" || (startswith(var.hosted_zone_id, "Z") && length(var.hosted_zone_id) >= 8)
    error_message = "hosted_zone_id must be empty or a Route 53 zone id (starts with Z)."
  }
}

variable "name_prefix" {
  type        = string
  description = "Short prefix for AWS resource names."
  default     = "c2-edge"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{0,20}$", var.name_prefix))
    error_message = "name_prefix must be lowercase alphanumeric and hyphens, max 21 characters."
  }
}

variable "cloudfront_price_class" {
  type        = string
  description = "CloudFront price class. PriceClass_100 is cheapest for a lab."
  default     = "PriceClass_100"

  validation {
    condition     = contains(["PriceClass_100", "PriceClass_200", "PriceClass_All"], var.cloudfront_price_class)
    error_message = "cloudfront_price_class must be PriceClass_100, PriceClass_200, or PriceClass_All."
  }
}

variable "decoy_force_destroy" {
  type        = bool
  description = "Allow terraform destroy to empty the decoy bucket. Default true because this is a lab."
  default     = true
}

variable "extra_tags" {
  type        = map(string)
  description = "Optional extra tags merged onto all resources."
  default     = {}
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR. Lab default matches BUILD.md."
  default     = "10.42.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr must be a valid IPv4 CIDR."
  }
}

variable "public_subnet_cidr" {
  type        = string
  description = "Public subnet for the redirector. Must be inside vpc_cidr and not overlap private_subnet_cidr."
  default     = "10.42.1.0/24"

  validation {
    condition     = can(cidrnetmask(var.public_subnet_cidr))
    error_message = "public_subnet_cidr must be a valid IPv4 CIDR."
  }
}

variable "private_subnet_cidr" {
  type        = string
  description = "Private subnet for the teamserver and SSM endpoints. No NAT."
  default     = "10.42.2.0/24"

  validation {
    condition     = can(cidrnetmask(var.private_subnet_cidr))
    error_message = "private_subnet_cidr must be a valid IPv4 CIDR."
  }
}

variable "availability_zone" {
  type        = string
  description = "AZ for both subnets. Empty uses the first commercial (opt-in-not-required) AZ."
  default     = ""

  validation {
    condition     = var.availability_zone == "" || can(regex("^[a-z]{2}-[a-z]+-[0-9][a-z]$", var.availability_zone))
    error_message = "availability_zone must be empty or an AZ name such as us-east-1a."
  }
}

variable "teamserver_listen_port" {
  type        = number
  description = "Port nginx will proxy to on the private teamserver (echo stub / C2)."
  default     = 8080

  validation {
    condition     = var.teamserver_listen_port >= 1 && var.teamserver_listen_port <= 65535
    error_message = "teamserver_listen_port must be a valid TCP port."
  }
}

variable "instance_type" {
  type        = string
  description = "Instance type for both EC2s."
  default     = "t3.micro"
}

variable "root_volume_type" {
  type        = string
  description = "EBS type for both instances."
  default     = "gp3"

  validation {
    condition     = contains(["gp3", "gp2"], var.root_volume_type)
    error_message = "root_volume_type must be gp3 or gp2."
  }
}

variable "root_volume_size" {
  type        = number
  description = "Root volume size in GiB. Ubuntu 24.04 needs at least 8."
  default     = 8

  validation {
    condition     = var.root_volume_size >= 8 && var.root_volume_size <= 64
    error_message = "root_volume_size must be between 8 and 64 GiB."
  }
}

variable "cloudfront_minimum_protocol_version" {
  type        = string
  description = "Viewer TLS policy. TLSv1.2_2021 is the current AWS-recommended minimum."
  default     = "TLSv1.2_2021"

  validation {
    condition     = contains(["TLSv1.2_2019", "TLSv1.2_2021"], var.cloudfront_minimum_protocol_version)
    error_message = "cloudfront_minimum_protocol_version must be TLSv1.2_2019 or TLSv1.2_2021."
  }
}

variable "nginx_backend_placeholder" {
  type        = string
  description = "Must match --backend-host used by `make conf` (RFC 5737 TEST-NET). Terraform replaces it with the teamserver private IP."
  default     = "192.0.2.1"

  validation {
    condition     = can(cidrhost("${var.nginx_backend_placeholder}/32", 0))
    error_message = "nginx_backend_placeholder must be an IPv4 address (default 192.0.2.1)."
  }
}

variable "nginx_header_placeholder" {
  type        = string
  description = "Must match --header-value used by `make conf`. Terraform replaces it with random_password."
  default     = "PLACEHOLDERHEADER"

  validation {
    condition     = can(regex("^[A-Za-z0-9._~+/-]+$", var.nginx_header_placeholder))
    error_message = "nginx_header_placeholder must be a non-empty token safe for the nginx map."
  }
}

variable "callback_header_name" {
  type        = string
  description = "Must match header.name in policy/redirector.policy.yaml."
  default     = "X-Lab-Token"
}

variable "callback_path_patterns" {
  type        = list(string)
  description = "CloudFront ordered behaviors that go to nginx. Must match policy path prefixes (e.g. /cdn/ → /cdn/*). Not /* — that would steal the S3 decoy."
  default     = ["/cdn/*"]

  validation {
    condition = length(var.callback_path_patterns) > 0 && length(distinct(var.callback_path_patterns)) == length(var.callback_path_patterns) && alltrue([
      for pattern in var.callback_path_patterns :
      startswith(pattern, "/") && endswith(pattern, "/*") && pattern != "/*" && length(pattern) <= 255
    ])
    error_message = "callback_path_patterns must be unique CloudFront paths such as /cdn/*, ending in /*. Not /*."
  }
}

variable "longhaul_path_patterns" {
  type        = list(string)
  description = "Ordered behaviors on the *second* CloudFront hostname (long-haul). Separate dxxxx from the short-haul distribution."
  default     = ["/lh/*"]

  validation {
    condition = length(var.longhaul_path_patterns) > 0 && length(distinct(var.longhaul_path_patterns)) == length(var.longhaul_path_patterns) && alltrue([
      for pattern in var.longhaul_path_patterns :
      startswith(pattern, "/") && endswith(pattern, "/*") && pattern != "/*" && length(pattern) <= 255
    ])
    error_message = "longhaul_path_patterns must be unique CloudFront paths such as /lh/*, ending in /*. Not /*."
  }
}
