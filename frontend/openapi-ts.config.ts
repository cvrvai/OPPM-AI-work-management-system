import { defineConfig } from '@hey-api/openapi-ts'

export default defineConfig({
  input: 'intelligence-openapi.json',
  output: 'src/generated/intelligence-api',
  plugins: [
    '@hey-api/client-fetch',
    {
      name: '@hey-api/typescript',
      enums: 'typescript',
    },
  ],
})
