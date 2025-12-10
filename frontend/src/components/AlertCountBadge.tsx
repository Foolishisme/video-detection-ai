import { Chip } from '@mui/material';

interface AlertCountBadgeProps {
  count: number;
}

export function AlertCountBadge({ count }: AlertCountBadgeProps) {
  return (
    <Chip
      label={`告警: ${count}`}
      sx={{
        position: 'absolute',
        top: 10,
        left: 10,
        backgroundColor: 'rgba(0, 0, 0, 0.6)',
        color: '#fff',
        fontWeight: 'bold',
        zIndex: 10,
      }}
    />
  );
}

