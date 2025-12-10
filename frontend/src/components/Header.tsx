import { Box, Typography } from '@mui/material';

export function Header() {
  return (
    <Box
      sx={{
        height: '60px',
        backgroundColor: '#1a2332',
        display: 'flex',
        alignItems: 'center',
        paddingLeft: '20px',
        borderLeft: '4px solid #1976d2',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.3)',
      }}
    >
      <Typography
        variant="h5"
        sx={{
          color: '#fff',
          fontWeight: 'bold',
          letterSpacing: '1px',
        }}
      >
        AI 智能监控中心
      </Typography>
    </Box>
  );
}

