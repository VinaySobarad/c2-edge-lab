data "aws_iam_policy_document" "ec2_assume" {
  statement {
    sid     = "Ec2Assume"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ssm" {
  name_prefix        = "${var.name_prefix}-ssm-"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

data "aws_iam_policy" "ssm_core" {
  name = "AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.ssm.name
  policy_arn = data.aws_iam_policy.ssm_core.arn
}

resource "aws_iam_instance_profile" "ssm" {
  name_prefix = "${var.name_prefix}-ssm-"
  role        = aws_iam_role.ssm.name
}

# Teamserver is the only box that may pull staged objects. The redirector
# shares SSM, not this GetObject.
resource "aws_iam_role" "teamserver" {
  name_prefix        = "${var.name_prefix}-ts-"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "teamserver_ssm_core" {
  role       = aws_iam_role.teamserver.name
  policy_arn = data.aws_iam_policy.ssm_core.arn
}

resource "aws_iam_instance_profile" "teamserver" {
  name_prefix = "${var.name_prefix}-ts-"
  role        = aws_iam_role.teamserver.name
}

data "aws_iam_policy_document" "s3_stage" {
  statement {
    sid     = "GetStagedObject"
    effect  = "Allow"
    actions = ["s3:GetObject"]
    resources = [
      "${aws_s3_bucket.decoy.arn}/${local.stage_key_prefix}/*",
    ]
  }
}

resource "aws_iam_role_policy" "s3_stage" {
  name   = "s3-stage"
  role   = aws_iam_role.teamserver.id
  policy = data.aws_iam_policy_document.s3_stage.json
}
