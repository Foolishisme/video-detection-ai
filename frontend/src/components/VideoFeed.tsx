import { Box, CircularProgress, Typography, IconButton } from '@mui/material';
import { Fullscreen as FullscreenIcon, MoreVert as MoreVertIcon } from '@mui/icons-material';
import WarningIcon from '@mui/icons-material/Warning';
import { useState } from 'react';
import { getVideoFeedUrl } from '../api/api';

interface VideoFeedProps {
  sourceId: number;
  hasAlert?: boolean; // 是否有告警（显示红色覆盖层）
  cameraName?: string; // 摄像头名称
  alertMessage?: string; // 告警消息
}

export function VideoFeed({ 
  sourceId, 
  hasAlert = false, 
  cameraName,
  alertMessage 
}: VideoFeedProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const videoUrl = getVideoFeedUrl(sourceId);

  const handleLoad = () => {
    setLoading(false);
    setError(null);
  };

  const handleError = () => {
    setLoading(false);
    setError('视频流加载失败');
  };

  const displayName = cameraName || `摄像头 ${sourceId + 1}`;
  const cameraId = `CAM-${String(sourceId + 1).padStart(3, '0')}`;

  return (
    <Box
      sx={{
        position: 'relative',
        width: '100%',
        height: '100%',
        backgroundColor: '#000',
        borderRadius: '8px',
        overflow: 'hidden',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
      }}
    >
      {/* 视频流 */}
      {loading && (
        <Box
          sx={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            zIndex: 1,
          }}
        >
          <CircularProgress size={40} />
        </Box>
      )}
      {error ? (
        <Box
          sx={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            color: '#fff',
            textAlign: 'center',
            zIndex: 1,
          }}
        >
          <Typography variant="body1" color="error">
            {error}
          </Typography>
        </Box>
      ) : (
        <img
          src={videoUrl}
          alt={`视频源 ${sourceId}`}
          onLoad={handleLoad}
          onError={handleError}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            backgroundColor: '#000',
            display: loading ? 'none' : 'block',
          }}
        />
      )}

      {/* ONLINE 状态指示器 */}
      <Box
        sx={{
          position: 'absolute',
          top: 12,
          right: 12,
          backgroundColor: 'rgba(76, 175, 80, 0.9)',
          color: '#fff',
          padding: '4px 12px',
          borderRadius: '12px',
          fontSize: '12px',
          fontWeight: 'bold',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          zIndex: 10,
          boxShadow: '0 2px 4px rgba(0, 0, 0, 0.3)',
        }}
      >
        <Box
          sx={{
            width: '8px',
            height: '8px',
            backgroundColor: '#fff',
            borderRadius: '50%',
          }}
        />
        ONLINE
      </Box>

      {/* 危险告警覆盖层 */}
      {hasAlert && (
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(244, 67, 54, 0.5)',
            backdropFilter: 'blur(2px)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 15,
          }}
        >
          <WarningIcon
            sx={{
              fontSize: 60,
              color: '#ffc107',
              marginBottom: 2,
              filter: 'drop-shadow(0 2px 4px rgba(0, 0, 0, 0.5))',
            }}
          />
          <Typography
            sx={{
              color: '#fff',
              fontSize: '18px',
              fontWeight: 'bold',
              textAlign: 'center',
              textShadow: '2px 2px 4px rgba(0, 0, 0, 0.8)',
              padding: '0 20px',
            }}
          >
            {alertMessage || '检测到危险行为'}
          </Typography>
        </Box>
      )}

      {/* 底部信息栏 */}
      <Box
        sx={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          backgroundColor: 'rgba(26, 35, 50, 0.85)',
          backdropFilter: 'blur(4px)',
          padding: '10px 12px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          zIndex: 10,
        }}
      >
        <Typography
          sx={{
            color: '#fff',
            fontSize: '14px',
            fontWeight: 500,
          }}
        >
          {displayName} (ID: {cameraId})
        </Typography>
        <Box sx={{ display: 'flex', gap: '4px' }}>
          <IconButton 
            size="small" 
            sx={{ 
              color: '#fff',
              '&:hover': {
                backgroundColor: 'rgba(255, 255, 255, 0.1)',
              },
            }}
          >
            <FullscreenIcon fontSize="small" />
          </IconButton>
          <IconButton 
            size="small" 
            sx={{ 
              color: '#fff',
              '&:hover': {
                backgroundColor: 'rgba(255, 255, 255, 0.1)',
              },
            }}
          >
            <MoreVertIcon fontSize="small" />
          </IconButton>
        </Box>
      </Box>
    </Box>
  );
}

