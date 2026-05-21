export type Topology = {
  region: string;
  fetched_at: string;
  summary: {
    instance_count: number;
    running_count: number;
    vpc_count: number;
    subnet_count: number;
    security_group_count: number;
    open_inbound_0_0_0_0: number;
  };
  vpcs: Array<{ id: string; cidr?: string; name?: string; is_default?: boolean; state?: string }>;
  subnets: Array<{
    id: string;
    vpc_id?: string;
    cidr?: string;
    az?: string;
    name?: string;
    public?: boolean;
  }>;
  security_groups: Array<{
    id: string;
    vpc_id?: string;
    name?: string;
    description?: string;
    used_by_instances?: number;
    inbound?: Array<Record<string, unknown>>;
    outbound?: Array<Record<string, unknown>>;
  }>;
  instances: Array<{
    instance_id: string;
    name?: string;
    state?: string;
    instance_type?: string;
    vpc_id?: string;
    subnet_id?: string;
    az?: string;
    private_ip?: string;
    public_ip?: string;
    security_group_ids?: string[];
    eni_ids?: string[];
  }>;
  edges: Array<{ from: string; to: string; type: string }>;
};

export const LS_AWS_ROLE = "ide-aws-role-arn";
export const LS_AWS_REGION = "ide-aws-region";
export const LS_HOME_DISPLAY = "ide-home-display";
export const LS_INFRA_DISPLAY = "ide-infra-display";
