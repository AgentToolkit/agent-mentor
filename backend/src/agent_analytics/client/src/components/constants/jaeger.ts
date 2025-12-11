export interface JaegerSpan {
  traceID: string;
  spanID: string;
  operationName: string;
  references: JaegerReference[];
  startTime: number;
  duration: number;
  tags: JaegerTag[];
  logs?: JaegerLog[];
  processID: string;
  warnings?: string[];
}

export interface JaegerReference {
  refType: 'CHILD_OF' | 'FOLLOWS_FROM';
  traceID: string;
  spanID: string;
}

export interface JaegerTag {
  key: string;
  type: 'string' | 'bool' | 'int64' | 'float64' | 'binary';
  value: any;
}

export interface JaegerLog {
  timestamp: number;
  fields: JaegerTag[];
}

export interface JaegerProcess {
  serviceName: string;
  tags: JaegerTag[];
}

export interface JaegerTrace {
  traceID: string;
  spans: JaegerSpan[];
  processes: Record<string, JaegerProcess>;
  warnings?: string[];
}

export interface SpanNode extends JaegerSpan {
  depth: number;
  children: SpanNode[];
  hasChildren: boolean;
  isExpanded: boolean;
  service: string;
}
