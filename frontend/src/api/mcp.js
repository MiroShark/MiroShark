import service from './index'

/**
 * Get the MiroShark MCP server status, tool catalog, and per-client config
 * snippets. Used by the Settings → AI Integration panel to give users a
 * copy-paste path into Claude Desktop, Cursor, Windsurf, and Continue.
 *
 * @returns {Promise<{
 *   success: boolean,
 *   data: {
 *     enabled: boolean,
 *     transport: string,
 *     paths: { backend_dir: string, mcp_script: string, mcp_script_exists: boolean, python_executable: string },
 *     tools: Array<{ name: string, description: string }>,
 *     tool_count: number,
 *     clients: Object<string, { label: string, file: string, config: object, notes: string }>,
 *     neo4j: { connected: boolean, uri: string, user: string, graph_count: number|null, entity_count: number|null, error: string|null },
 *     docs_url: string,
 *   }
 * }>}
 */
export const getMcpStatus = () => {
  return service.get('/api/mcp/status')
}
