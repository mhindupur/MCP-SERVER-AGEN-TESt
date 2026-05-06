variable "project_name" {
  type    = string
  default = "ide-platform"
}

variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.30.0.0/16"
}

variable "azs" {
  type    = list(string)
  default = ["ap-south-1a", "ap-south-1b"]
}

variable "private_subnets" {
  type    = list(string)
  default = ["10.30.16.0/20", "10.30.32.0/20"]
}

variable "public_subnets" {
  type    = list(string)
  default = ["10.30.0.0/20", "10.30.8.0/20"]
}

variable "db_name" {
  type    = string
  default = "ide_platform"
}

variable "db_username" {
  type    = string
  default = "admin"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "api_image" {
  type        = string
  description = "ECR image URI for services/api"
}
