import type { SourceInfo, VideoSourceStatus, AlertsResponse } from '../types';

// API 基础 URL 配置
// 开发环境：使用相对路径，通过 Vite 代理转发到后端
// 生产环境：使用环境变量 VITE_API_BASE_URL，如果未设置则使用相对路径
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

/**
 * 获取视频源列表
 */
export async function getSources(): Promise<SourceInfo> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/sources`);
    if (!response.ok) {
      throw new Error(`Failed to fetch sources: ${response.status} ${response.statusText}`);
    }
    return response.json();
  } catch (error) {
    console.error('获取视频源列表失败:', error);
    throw error;
  }
}

/**
 * 获取视频流 URL
 */
export function getVideoFeedUrl(sourceId: number): string {
  return `${API_BASE_URL}/api/video_feed/${sourceId}`;
}

/**
 * 获取视频源状态
 */
export async function getStatus(sourceId: number): Promise<VideoSourceStatus> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/status/${sourceId}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch status for source ${sourceId}: ${response.status} ${response.statusText}`);
    }
    return response.json();
  } catch (error) {
    console.error(`获取视频源 ${sourceId} 状态失败:`, error);
    throw error;
  }
}

/**
 * 获取告警列表
 */
export async function getAlerts(): Promise<AlertsResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/alerts`);
    if (!response.ok) {
      throw new Error(`Failed to fetch alerts: ${response.status} ${response.statusText}`);
    }
    return response.json();
  } catch (error) {
    console.error('获取告警列表失败:', error);
    throw error;
  }
}

