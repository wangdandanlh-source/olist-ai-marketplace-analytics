import {defineConfig} from 'vite';
export default defineConfig({base:'./',build:{sourcemap:false,rollupOptions:{output:{manualChunks:{charts:['echarts/core','echarts/charts','echarts/components','echarts/renderers'],react:['react','react-dom/client']}}}}});
