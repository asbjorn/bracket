import react from '@vitejs/plugin-react';
import tsconfigPaths from 'vite-tsconfig-paths';

import { defineConfig } from 'vite';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tsconfigPaths()],
  define: {
    // Changes with every build; used to load new translation files after a deploy
    __BUILD_VERSION__: JSON.stringify(Date.now().toString(36)),
  },
});
