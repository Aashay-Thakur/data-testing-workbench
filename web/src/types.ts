export type Run = {
  id: number;
  check_id: number | null;
  name: string | null;
  kind: string;
  status: string;
  blocking: boolean;
  threshold: Record<string, unknown>;
  sample: Record<string, unknown>[];
  metrics: Record<string, unknown>;
  message: string | null;
  runtime_ms: number | null;
  sql_hash: string | null;
  git_sha: string | null;
  target: string | null;
  created_at: string;
};

export type Check = {
  id: number;
  name: string;
  kind: string;
  label: string;
  origin: string;
  target: {
    database?: string | null;
    schema_name?: string | null;
    relation?: string | null;
    unique_id?: string | null;
  };
  params: Record<string, unknown>;
  blocking: boolean;
  created_at: string;
};

export type KindInfo = {
  kind: string;
  title: string;
  plain: string;
  fields: string[];
};

export type CatalogNode = {
  unique_id: string;
  name: string;
  resource_type: string;
  database?: string | null;
  schema_name?: string | null;
  alias?: string | null;
  original_file_path?: string | null;
  description?: string;
};

export type Catalog = {
  models: CatalogNode[];
  sources: CatalogNode[];
  snapshots: CatalogNode[];
  tests: CatalogNode[];
  counts: Record<string, number>;
};
