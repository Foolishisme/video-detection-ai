import { Grid, Box, useMediaQuery, useTheme } from '@mui/material';
import { VideoFeed } from './VideoFeed';
import { AlertCountBadge } from './AlertCountBadge';
import { getCameraName } from '../config/cameraNames';
import type { Alert } from '../types';

interface VideoGridProps {
  sourceCount: number;
  alertCounts: Record<number, number>; // sourceId -> alertCount
  windowWarnings: Record<number, Alert | null>; // sourceId -> alert
  alertStates: Record<number, boolean>; // sourceId -> hasAlert (for border blinking)
}

export function VideoGrid({
  sourceCount,
  alertCounts,
  windowWarnings,
  alertStates,
}: VideoGridProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const isTablet = useMediaQuery(theme.breakpoints.down('md'));

  // 根据视频源数量和屏幕尺寸动态计算网格大小
  const getGridSize = (count: number): number => {
    if (count === 0) return 1;
    if (count === 1) return 1;
    
    // 移动端：单列布局
    if (isMobile) {
      return 1;
    }
    
    // 平板：最多2列
    if (isTablet) {
      if (count <= 2) return 1;
      return 2;
    }
    
    // 桌面端：根据数量动态调整
    if (count <= 4) return 2;
    if (count <= 9) return 3;
    return 3; // 最多显示 9 个
  };

  const gridSize = getGridSize(sourceCount);
  const maxSources = Math.min(sourceCount, 9);

  return (
    <Grid
      container
      spacing={2}
      sx={{
        width: '100%',
        height: 'calc(100vh - 60px)',
        padding: 2,
        backgroundColor: '#0f1419',
      }}
    >
      {Array.from({ length: maxSources }, (_, index) => {
        const sourceId = index;
        const alertCount = alertCounts[sourceId] || 0;
        const windowWarning = windowWarnings[sourceId] || null;
        const hasAlert = alertStates[sourceId] || false;

        return (
          <Grid
            item
            xs={isMobile ? 12 : 12 / gridSize}
            sm={isTablet && !isMobile ? 6 : undefined}
            md={!isTablet ? 12 / gridSize : undefined}
            key={sourceId}
            sx={{
              height: isMobile 
                ? 'auto' 
                : `calc((100vh - 60px - ${(gridSize + 1) * 16}px) / ${gridSize})`,
              minHeight: isMobile ? '200px' : 0,
              aspectRatio: isMobile ? '16/9' : 'auto',
            }}
          >
            <Box
              sx={{
                position: 'relative',
                width: '100%',
                height: '100%',
              }}
            >
              <VideoFeed 
                sourceId={sourceId} 
                hasAlert={hasAlert}
                alertMessage={windowWarning?.message || '检测到危险行为'}
                cameraName={getCameraName(sourceId)}
              />
              <AlertCountBadge count={alertCount} />
            </Box>
          </Grid>
        );
      })}
    </Grid>
  );
}

