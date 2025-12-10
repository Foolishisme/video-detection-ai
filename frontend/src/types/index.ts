// API 响应类型定义

export interface SourceInfo {
  source_count: number;
  sources: number[];
}

export interface VideoSourceStatus {
  fps: number;
  status: string;
  alert_count: number;
  analysis_count: number;
  person_detection_count: number;
  connection_status: string;
  cpu_percent?: number;
  error?: string;
}

export interface Alert {
  id: number;
  source_id: number;
  timestamp: string;
  type: string;
  message: string;
  severity: 'high' | 'low' | 'safe';
  reasoning?: string;
  confidence?: number;
  is_danger: boolean;
  image_path?: string;
}

export interface AlertsResponse {
  alerts: Alert[];
}

