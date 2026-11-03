import { sveltekit } from '@sveltejs/kit/vite';
import adapter from '@sveltejs/adapter-static';
import { defineConfig } from 'vite';
export default defineConfig({plugins:[sveltekit({csp:{mode:'hash',directives:{'script-src':['self']}},adapter:adapter({fallback:'index.html'})})],server:{proxy:{'/api':'http://127.0.0.1:8088'}}});
