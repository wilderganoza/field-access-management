/* ============================================= */
/* UTILIDADES PARA MANEJO DE ARCHIVOS            */
/* Incluye: íconos, tamaños, descompresión       */
/* y parsing de archivos .eml                    */
/* ============================================= */
import JSZip from 'jszip';
import { apiExtractRar } from './api';

/* Extensiones aceptadas por la aplicación */
export const ACCEPTED_EXTENSIONS = [
  '.eml', '.pdf', '.docx', '.doc', '.xlsx', '.xls',
  '.png', '.jpg', '.jpeg', '.zip', '.txt', '.rar', '.7zip', '.7z'
];

/* Tipo MIME correspondiente para el input de archivos */
export const ACCEPT_STRING = ACCEPTED_EXTENSIONS.join(',');

/* Mapa de íconos por extensión de archivo */
const FILE_ICONS = {
  '.eml': '📧',
  '.pdf': '📄',
  '.docx': '📝',
  '.doc': '📝',
  '.xlsx': '📊',
  '.xls': '📊',
  '.png': '🖼️',
  '.jpg': '🖼️',
  '.jpeg': '🖼️',
  '.zip': '📦',
  '.rar': '📦',
  '.7zip': '📦',
  '.7z': '📦',
  '.txt': '📃',
};

/* Obtener ícono según la extensión del archivo */
export function getFileIcon(filename) {
  /* Extraer la extensión del nombre del archivo */
  const ext = '.' + filename.split('.').pop().toLowerCase();
  /* Retornar el ícono o uno genérico si no se encuentra */
  return FILE_ICONS[ext] || '📎';
}

/* Formatear tamaño de archivo en unidades legibles */
export function formatFileSize(bytes) {
  /* Si es menor a 1 KB, mostrar en bytes */
  if (bytes < 1024) return bytes + ' B';
  /* Si es menor a 1 MB, mostrar en KB */
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  /* Si es mayor, mostrar en MB */
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/* Obtener la extensión de un archivo */
export function getExtension(filename) {
  return '.' + filename.split('.').pop().toLowerCase();
}

/* Verificar si un archivo es comprimido */
export function isCompressed(filename) {
  const ext = getExtension(filename);
  return ['.zip', '.rar', '.7zip', '.7z'].includes(ext);
}

/* Verificar si un archivo es temporal (prefijo ~$) */
export function isTempFile(filename) {
  const name = filename.split('/').pop().split('\\').pop();
  return name.startsWith('~$') || name.startsWith('.');
}

/* Verificar si un archivo es una imagen */
export function isImage(filename) {
  const ext = getExtension(filename);
  return ['.png', '.jpg', '.jpeg'].includes(ext);
}

/* Verificar si un archivo es PDF */
export function isPDF(filename) {
  return getExtension(filename) === '.pdf';
}

/* ============================================= */
/* DESCOMPRESIÓN DE ARCHIVOS ZIP                 */
/* Soporta 1 nivel de anidamiento                */
/* ============================================= */
export async function decompressFile(file) {
  /* Array para almacenar los archivos extraídos */
  const extracted = [];
  const ext = getExtension(file.name);

  try {
    /* RAR: extraer en el servidor */
    if (ext === '.rar') {
      const result = await apiExtractRar(file);
      for (const entry of result.files) {
        /* Saltar archivos temporales */
        if (isTempFile(entry.name)) continue;
        /* Verificar extensión aceptada */
        const entryExt = getExtension(entry.name);
        if (!ACCEPTED_EXTENSIONS.includes(entryExt)) continue;
        /* Convertir base64 a File */
        const binary = atob(entry.base64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        const blob = new Blob([bytes], { type: 'application/octet-stream' });
        const extractedFile = new File([blob], entry.name, { type: blob.type });
        extracted.push({ file: extractedFile, origin: file.name });
      }
      return extracted;
    }

    /* ZIP: extraer en el navegador con JSZip */
    const zip = await JSZip.loadAsync(file);
    /* Iterar sobre cada archivo dentro del ZIP */
    for (const [relativePath, zipEntry] of Object.entries(zip.files)) {
      /* Saltar directorios */
      if (zipEntry.dir) continue;
      /* Obtener el nombre del archivo sin la ruta */
      const name = relativePath.split('/').pop();
      /* Saltar archivos temporales */
      if (isTempFile(name)) continue;
      /* Verificar si la extensión es aceptada */
      const entryExt = getExtension(name);
      if (!ACCEPTED_EXTENSIONS.includes(entryExt)) continue;
      /* Extraer el contenido como blob */
      const blob = await zipEntry.async('blob');
      /* Crear un objeto File a partir del blob */
      const extractedFile = new File([blob], name, { type: blob.type || 'application/octet-stream' });
      /* Verificar si el archivo extraído es también un comprimido (1 nivel) */
      if (isCompressed(name)) {
        try {
          /* Intentar descomprimir el archivo anidado */
          const nestedFiles = await decompressNestedZip(blob, name);
          /* Agregar archivos anidados con referencia al comprimido padre */
          nestedFiles.forEach(nf => {
            extracted.push({ file: nf, origin: `${file.name} > ${name}` });
          });
        } catch {
          /* Si falla la descompresión anidada, tratar como archivo normal */
          extracted.push({ file: extractedFile, origin: file.name });
        }
      } else {
        /* Agregar el archivo extraído con su origen */
        extracted.push({ file: extractedFile, origin: file.name });
      }
    }
  } catch {
    /* Si falla la descompresión, retornar array vacío */
    return [];
  }
  return extracted;
}

/* Descomprimir un ZIP anidado (segundo nivel) */
async function decompressNestedZip(blob, parentName) {
  /* Array para almacenar los archivos del ZIP anidado */
  const files = [];
  /* Cargar el ZIP anidado */
  const zip = await JSZip.loadAsync(blob);
  /* Iterar sobre cada archivo */
  for (const [relativePath, zipEntry] of Object.entries(zip.files)) {
    /* Saltar directorios y comprimidos (no más niveles) */
    if (zipEntry.dir) continue;
    const name = relativePath.split('/').pop();
    const ext = getExtension(name);
    /* Solo extraer extensiones aceptadas y no comprimidas */
    if (!ACCEPTED_EXTENSIONS.includes(ext) || isCompressed(name)) continue;
    /* Extraer contenido como blob */
    const nestedBlob = await zipEntry.async('blob');
    /* Crear objeto File */
    files.push(new File([nestedBlob], name, { type: nestedBlob.type || 'application/octet-stream' }));
  }
  return files;
}

/* ============================================= */
/* PARSER DE ARCHIVOS .EML                       */
/* Extrae: from, to, subject, date, body y       */
/* archivos adjuntos                             */
/* ============================================= */
export async function parseEmlFile(file) {
  /* Importar postal-mime dinámicamente */
  const PostalMime = (await import('postal-mime')).default;
  /* Leer el contenido del archivo como ArrayBuffer */
  const buffer = await file.arrayBuffer();
  /* Crear instancia del parser */
  const parser = new PostalMime();
  /* Parsear el email */
  const email = await parser.parse(buffer);
  /* Extraer los adjuntos como objetos File */
  const attachments = (email.attachments || []).map(att => {
    /* Crear un File a partir del contenido del adjunto */
    const blob = new Blob([att.content], { type: att.mimeType });
    return new File([blob], att.filename || 'adjunto', { type: att.mimeType });
  });
  /* Retornar los datos parseados del correo */
  return {
    from: email.from?.text || email.from?.value?.[0]?.address || 'Desconocido',
    to: email.to?.text || email.to?.value?.[0]?.address || 'Desconocido',
    subject: email.subject || 'Sin asunto',
    date: email.date || 'Sin fecha',
    body: email.text || email.html?.replace(/<[^>]+>/g, ' ') || 'Sin contenido',
    attachments,
  };
}

/* Convertir un File a base64 para enviar a la API */
export function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    /* Crear un FileReader para leer el archivo */
    const reader = new FileReader();
    /* Al completar la lectura, extraer el base64 */
    reader.onload = () => {
      const base64 = reader.result.split(',')[1];
      resolve(base64);
    };
    /* Manejar errores de lectura */
    reader.onerror = reject;
    /* Iniciar la lectura como Data URL */
    reader.readAsDataURL(file);
  });
}

/* Limpiar respuesta JSON de OpenAI (puede venir con backticks markdown) */
export function cleanJsonResponse(text) {
  /* Remover bloques de código markdown y espacios en blanco */
  return text.replace(/```json|```/g, '').trim();
}
