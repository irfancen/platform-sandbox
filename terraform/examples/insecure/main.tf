# DO NOT APPLY. Known-bad fixture proving the IaC gate blocks Task 3 scenarios A and B.

resource "aws_iam_role" "deploy" {
  name = "insecure-deploy"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "deploy" {
  name = "admin"
  role = aws_iam_role.deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "*"
      Resource = "*"
    }]
  })
}

resource "aws_security_group" "db" {
  name = "insecure-db"

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_instance" "app" {
  identifier                  = "insecure-db"
  engine                      = "postgres"
  instance_class              = "db.t3.micro"
  allocated_storage           = 20
  username                    = "app"
  manage_master_user_password = true
  publicly_accessible         = true
  vpc_security_group_ids      = [aws_security_group.db.id]
  skip_final_snapshot         = true
}
