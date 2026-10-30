export function formatearFecha(iso: string | null | undefined): string {
  if (!iso) return '';
  return new Date(iso).toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'short' });
}
