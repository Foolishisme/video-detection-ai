import { Alert, Box } from '@mui/material';
import { useEffect, useState } from 'react';

interface WindowWarningProps {
  alert: {
    type: string;
    message: string;
    timestamp: string;
  } | null;
  duration?: number; // 显示时长（毫秒）
}

export function WindowWarning({ alert, duration = 10000 }: WindowWarningProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (alert) {
      setVisible(true);
      const timer = setTimeout(() => {
        setVisible(false);
      }, duration);
      return () => clearTimeout(timer);
    } else {
      setVisible(false);
    }
  }, [alert, duration]);

  if (!alert || !visible) {
    return null;
  }

  return (
    <Box
      sx={{
        position: 'absolute',
        bottom: 10,
        left: 10,
        right: 10,
        zIndex: 20,
      }}
    >
      <Alert
        severity="warning"
        sx={{
          backgroundColor: 'rgba(255, 193, 7, 0.9)',
          color: '#000',
          fontWeight: 'bold',
          '& .MuiAlert-icon': {
            color: '#000',
          },
        }}
      >
        <strong>{alert.type}</strong>: {alert.message}
      </Alert>
    </Box>
  );
}

