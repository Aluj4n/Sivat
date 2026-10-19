// El backend guarda el titular en la primera línea y el cuerpo debajo
export function titularDe(texto: string): string {
  return texto.split('\n').find((linea) => linea.trim())?.trim() ?? texto;
}
