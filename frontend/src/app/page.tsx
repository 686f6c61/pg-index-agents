/**
 * PG Index Agents - Pagina principal
 * https://github.com/686f6c61/pg-index-agents
 *
 * Pagina de inicio que muestra el listado de bases de datos registradas.
 * Renderiza el componente DatabaseList que permite ver, agregar y
 * acceder a cada base de datos para su analisis.
 *
 * @author 686f6c61
 * @license MIT
 */

import { DatabaseList } from "@/components/databases/DatabaseList";

/** Componente de pagina principal */
export default function Home() {
  return <DatabaseList />;
}
