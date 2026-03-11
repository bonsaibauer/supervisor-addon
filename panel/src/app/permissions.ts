export type AppPermission =
  | 'admin'
  | 'server.read'
  | 'server.control'
  | 'logs.read'
  | 'files.read'
  | 'files.write'
  | 'activity.read'
  | 'news.read';

export function canPermissions(permissions: string[] | undefined, permission: AppPermission): boolean {
  const effective = new Set((permissions || []).map((value) => value.trim()).filter(Boolean));
  return effective.has('admin') || effective.has(permission);
}
