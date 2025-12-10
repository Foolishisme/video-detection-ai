import { Dialog, DialogContent, Typography, Box } from '@mui/material';
import { Warning } from '@mui/icons-material';
import { useEffect, useState } from 'react';
import type { Alert } from '../types';

interface FullscreenAlertDialogProps {
  alert: Alert | null;
  duration?: number; // 显示时长（毫秒）
  onClose?: () => void;
}

export function FullscreenAlertDialog({
  alert,
  duration = 5000,
  onClose,
}: FullscreenAlertDialogProps) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (alert) {
      setOpen(true);
      const timer = setTimeout(() => {
        setOpen(false);
        onClose?.();
      }, duration);
      return () => clearTimeout(timer);
    } else {
      setOpen(false);
    }
  }, [alert, duration, onClose]);

  return (
    <Dialog
      open={open}
      fullScreen
      PaperProps={{
        sx: {
          backgroundColor: 'rgba(220, 20, 60, 0.95)',
          color: '#fff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        },
      }}
    >
      <DialogContent>
        <Box
          sx={{
            textAlign: 'center',
            padding: 4,
          }}
        >
          <Warning sx={{ fontSize: 80, mb: 3 }} />
          <Typography variant="h1" sx={{ fontSize: 48, mb: 2, textShadow: '2px 2px 4px rgba(0, 0, 0, 0.5)' }}>
            危险告警
          </Typography>
          <Typography variant="h2" sx={{ fontSize: 36, mb: 2, fontWeight: 'bold' }}>
            {alert?.type || '危险'}
          </Typography>
          <Typography variant="h3" sx={{ fontSize: 24, mb: 1 }}>
            {alert?.message || '检测到危险情况'}
          </Typography>
          {alert?.timestamp && (
            <Typography variant="body1" sx={{ fontSize: 18, opacity: 0.9 }}>
              时间: {alert.timestamp}
            </Typography>
          )}
        </Box>
      </DialogContent>
    </Dialog>
  );
}

