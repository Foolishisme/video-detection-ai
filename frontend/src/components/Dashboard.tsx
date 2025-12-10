import { useState, useEffect, useCallback } from 'react';
import { Box, CircularProgress, Typography, Alert } from '@mui/material';
import { VideoGrid } from './VideoGrid';
import { FullscreenAlertDialog } from './FullscreenAlertDialog';
import { Header } from './Header';
import { getSources, getStatus, getAlerts } from '../api/api';
import type { Alert as AlertType } from '../types';

export function Dashboard() {
  const [sourceCount, setSourceCount] = useState(0);
  const [alertCounts, setAlertCounts] = useState<Record<number, number>>({});
  const [windowWarnings, setWindowWarnings] = useState<Record<number, AlertType | null>>({});
  const [alertStates, setAlertStates] = useState<Record<number, boolean>>({});
  const [fullscreenAlert, setFullscreenAlert] = useState<AlertType | null>(null);
  const [processedAlertIds, setProcessedAlertIds] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 初始化：获取视频源列表
  const initializeSources = useCallback(async () => {
    try {
      const sources = await getSources();
      setSourceCount(sources.source_count || 0);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch sources:', err);
      setError('无法获取视频源列表');
    } finally {
      setLoading(false);
    }
  }, []);

  // 更新告警次数
  const updateAlertCounts = useCallback(async () => {
    if (sourceCount === 0) return;

    const counts: Record<number, number> = {};
    const promises = [];

    for (let i = 0; i < sourceCount; i++) {
      promises.push(
        getStatus(i)
          .then((status) => {
            counts[i] = status.alert_count || 0;
          })
          .catch((err) => {
            console.error(`Failed to fetch status for source ${i}:`, err);
            counts[i] = 0;
          })
      );
    }

    await Promise.all(promises);
    setAlertCounts(counts);
  }, [sourceCount]);

  // 检查新告警
  const checkNewAlerts = useCallback(async () => {
    try {
      const response = await getAlerts();
      const alerts = response.alerts || [];

      // 检查新告警
      for (const alert of alerts) {
        const alertId = alert.id;

        // 如果已经处理过，跳过
        if (processedAlertIds.has(alertId)) {
          continue;
        }

        // 标记为已处理
        setProcessedAlertIds((prev) => {
          const newSet = new Set(prev);
          newSet.add(alertId);
          // 只保留最近100个告警ID
          if (newSet.size > 100) {
            const idsArray = Array.from(newSet);
            return new Set(idsArray.slice(-100));
          }
          return newSet;
        });

        const sourceId = alert.source_id !== undefined ? alert.source_id : 0;
        const severity = alert.severity || 'safe';
        const isDanger = alert.is_danger || false;

        // 危险动作：全屏弹窗 + 边框闪烁
        if (severity === 'high' && isDanger) {
          setFullscreenAlert(alert);
          // 设置边框闪烁状态（3秒后自动关闭）
          setAlertStates((prev) => ({
            ...prev,
            [sourceId]: true,
          }));
          setTimeout(() => {
            setAlertStates((prev) => ({
              ...prev,
              [sourceId]: false,
            }));
          }, 3000);
        }
        // 提醒类：小窗口警告
        else if (severity === 'low') {
          setWindowWarnings((prev) => ({
            ...prev,
            [sourceId]: alert,
          }));
        }
      }
    } catch (err) {
      console.error('Failed to check alerts:', err);
    }
  }, [processedAlertIds]);

  // 初始化
  useEffect(() => {
    initializeSources();
  }, [initializeSources]);

  // 定时更新告警次数（每2秒）
  useEffect(() => {
    if (sourceCount === 0) return;

    updateAlertCounts();
    const interval = setInterval(updateAlertCounts, 2000);
    return () => clearInterval(interval);
  }, [sourceCount, updateAlertCounts]);

  // 定时检查新告警（每1秒）
  useEffect(() => {
    checkNewAlerts();
    const interval = setInterval(checkNewAlerts, 1000);
    return () => clearInterval(interval);
  }, [checkNewAlerts]);

  if (loading) {
    return (
      <Box sx={{ backgroundColor: '#0f1419', minHeight: '100vh' }}>
        <Header />
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: 'calc(100vh - 60px)',
          }}
        >
          <CircularProgress />
        </Box>
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ backgroundColor: '#0f1419', minHeight: '100vh' }}>
        <Header />
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: 'calc(100vh - 60px)',
            padding: 2,
          }}
        >
          <Alert severity="error">{error}</Alert>
        </Box>
      </Box>
    );
  }

  if (sourceCount === 0) {
    return (
      <Box sx={{ backgroundColor: '#0f1419', minHeight: '100vh' }}>
        <Header />
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: 'calc(100vh - 60px)',
          }}
        >
          <Typography variant="h5" color="text.secondary">
            暂无视频源
          </Typography>
        </Box>
      </Box>
    );
  }

  return (
    <Box sx={{ backgroundColor: '#0f1419', minHeight: '100vh' }}>
      <Header />
      <VideoGrid
        sourceCount={sourceCount}
        alertCounts={alertCounts}
        windowWarnings={windowWarnings}
        alertStates={alertStates}
      />
      <FullscreenAlertDialog
        alert={fullscreenAlert}
        onClose={() => setFullscreenAlert(null)}
      />
    </Box>
  );
}

