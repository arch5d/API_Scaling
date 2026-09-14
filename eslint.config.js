import js from '@eslint/js';

export default [
  { ignores: ['node_modules/', 'coverage/', 'dist/'] },
  js.configs.recommended,
  {
    files: ['**/*.js'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        console: 'readonly',
        process: 'readonly'
      }
    },
    rules: {
      'no-unused-vars': ['error', { argsIgnorePattern: '^_' }]
    }
  },
  {
    files: ['loadtest/**/*.js'],
    languageOptions: {
      globals: {
        __ENV: 'readonly',
        __VU: 'readonly',
        __ITER: 'readonly'
      }
    }
  }
];
