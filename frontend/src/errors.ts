export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Perubahan gagal disimpan. Coba lagi.'
}
