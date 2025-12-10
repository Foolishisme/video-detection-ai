import { ThemeProvider, CssBaseline } from '@mui/material';
import { darkTheme } from './theme';
import { Dashboard } from './components/Dashboard';

function App() {
  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <Dashboard />
    </ThemeProvider>
  );
}

export default App;
