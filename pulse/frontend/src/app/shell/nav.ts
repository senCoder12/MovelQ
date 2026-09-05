/** The application's views. One table, read by the rail, the top bar's title
 * slot and the command palette, so a new view is added in exactly one place. */
export interface NavItem {
  label: string;
  path: string;
  icon: string;
  /** Rail grouping. Items with no section sit in the primary block at the top. */
  section?: string;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { label: 'Brief', path: '/brief', icon: 'thunderbolt' },
  { label: 'Insights', path: '/insights', icon: 'bar-chart' },
  { label: 'Reports', path: '/reports/leadership', icon: 'file-text' },
  { label: 'Data quality', path: '/data-quality', icon: 'safety-certificate' },
  { label: 'Fleet vendors', path: '/vendors', icon: 'bank', section: 'Management' },
  { label: 'Audit trail', path: '/audit', icon: 'clock-circle', section: 'Management' },
  { label: 'Action approvals', path: '/actions/audit', icon: 'send', section: 'Management' },
];

/** Rail groups in render order: the unlabelled primary block, then each section. */
export interface NavGroup {
  section: string | null;
  items: NavItem[];
}

export const NAV_GROUPS: readonly NavGroup[] = buildGroups(NAV_ITEMS);

function buildGroups(items: readonly NavItem[]): NavGroup[] {
  const groups: NavGroup[] = [];
  for (const item of items) {
    const section = item.section ?? null;
    const last = groups[groups.length - 1];
    if (last && last.section === section) {
      last.items.push(item);
    } else {
      groups.push({ section, items: [item] });
    }
  }
  return groups;
}
