check "subnets_do_not_overlap" {
  assert {
    condition = (
      var.public_subnet_cidr != var.private_subnet_cidr && (
        local.public_newbits == local.private_newbits ? true : (
          local.public_newbits < local.private_newbits
          ? !contains([for i in range(pow(2, local.private_newbits - local.public_newbits)) : cidrsubnet(var.public_subnet_cidr, local.private_newbits - local.public_newbits, i)], var.private_subnet_cidr)
          : !contains([for i in range(pow(2, local.public_newbits - local.private_newbits)) : cidrsubnet(var.private_subnet_cidr, local.public_newbits - local.private_newbits, i)], var.public_subnet_cidr)
        )
      )
    )
    error_message = "public_subnet_cidr and private_subnet_cidr must not overlap."
  }
}

check "nginx_placeholders_are_in_rendered_conf" {
  assert {
    condition = (
      strcontains(local.nginx_in, var.nginx_backend_placeholder) &&
      strcontains(local.nginx_in, var.nginx_header_placeholder) &&
      strcontains(local.nginx_in, ":${var.teamserver_listen_port}") &&
      strcontains(local.nginx_in, format("$%s", local.nginx_header_var)) &&
      alltrue([
        for prefix in local.policy.paths.prefixes :
        strcontains(local.nginx_in, "location ${prefix}")
      ])
    )
    error_message = "terraform/templates/redirector.conf.in is stale versus tfvars/policy. Run make conf."
  }
}

check "cloudfront_paths_cover_policy_prefixes" {
  assert {
    condition = alltrue([
      for prefix in local.policy.paths.prefixes : anytrue([
        for pattern in concat(var.callback_path_patterns, var.longhaul_path_patterns) :
        startswith(prefix, trimsuffix(replace(pattern, "*", ""), "/"))
      ])
    ])
    error_message = "Every policy path prefix must be covered by callback_path_patterns or longhaul_path_patterns."
  }
}

check "haul_path_patterns_are_disjoint" {
  assert {
    condition = length(
      setintersection(toset(var.callback_path_patterns), toset(var.longhaul_path_patterns))
    ) == 0
    error_message = "callback_path_patterns and longhaul_path_patterns must not share the same path."
  }
}

check "custom_domain_is_all_or_nothing" {
  assert {
    condition     = (var.domain_name == "") == (var.hosted_zone_id == "")
    error_message = "Set both domain_name and hosted_zone_id, or leave both empty to use the CloudFront default hostname."
  }
}

check "policy_yaml_matches_tfvars" {
  assert {
    condition = (
      local.policy.header.name == var.callback_header_name &&
      local.policy.backend.port == var.teamserver_listen_port &&
      length(try(local.policy.user_agents.allow_exact, [])) > 0
    )
    error_message = "policy YAML header.name, backend.port, and user_agents.allow_exact[0] must be set (header/port must match tfvars)."
  }
}

check "echo_body_is_template_safe" {
  assert {
    condition     = can(regex("^[A-Za-z0-9._-]+$", local.echo_body))
    error_message = "echo_body must be a simple token so it can sit in the teamserver Python literal."
  }
}

check "teamserver_user_data_fits_ec2" {
  assert {
    # base64gzip is already base64(gzip(bytes)). Decode is binary, so compare the
    # base64 length: 16384 bytes → 21848 characters (4 * ceil(16384/3)).
    condition     = length(base64gzip(local.teamserver_user_data)) <= 21848
    error_message = "Gzipped teamserver user_data exceeds the 16 KiB EC2 limit."
  }
}
