import { createTheme } from '@mui/material/styles';

// 创建暗色主题
export const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    error: {
      main: '#dc143c', // 危险告警红色
    },
    warning: {
      main: '#ffc107', // 提醒告警黄色
    },
    background: {
      default: '#0f1419',
      paper: '#1a2332',
    },
    text: {
      primary: '#ffffff',
      secondary: '#b0b0b0',
    },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: '#0f1419',
          overflow: 'hidden',
        },
      },
    },
  },
});

