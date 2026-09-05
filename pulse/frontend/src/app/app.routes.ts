import { Routes } from '@angular/router';

import { ActionsAuditPageComponent } from './features/actions/audit/actions-audit-page.component';
import { AuditPageComponent } from './features/audit/audit-page.component';
import { DispatchHistoryPageComponent } from './features/reports/history/dispatch-history-page.component';
import { BriefPageComponent } from './features/brief/brief-page.component';
import { DataQualityPageComponent } from './features/data-quality/data-quality-page.component';
import { InsightsPageComponent } from './features/insights/insights-page.component';
import { LeadershipPackPageComponent } from './features/leadership-pack/leadership-pack-page.component';
import { VendorsPageComponent } from './features/vendors/vendors-page.component';

/** `data.viewTitle` is what the top bar's left slot renders and what the command
 * palette lists -- the rail, the top bar and the palette all read this one table. */
export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'brief' },
  { path: 'brief', component: BriefPageComponent, data: { viewTitle: 'Executive brief' } },
  { path: 'insights', component: InsightsPageComponent, data: { viewTitle: 'Fleet insights' } },
  { path: 'reports', pathMatch: 'full', redirectTo: 'reports/leadership' },
  {
    path: 'reports/leadership',
    component: LeadershipPackPageComponent,
    data: { viewTitle: 'Reports' },
  },
  {
    path: 'reports/history',
    component: DispatchHistoryPageComponent,
    data: { viewTitle: 'Dispatch history' },
  },
  {
    path: 'data-quality',
    component: DataQualityPageComponent,
    data: { viewTitle: 'Data quality' },
  },
  { path: 'vendors', component: VendorsPageComponent, data: { viewTitle: 'Fleet vendors' } },
  { path: 'audit', component: AuditPageComponent, data: { viewTitle: 'Audit trail' } },
  {
    path: 'actions/audit',
    component: ActionsAuditPageComponent,
    data: { viewTitle: 'Action approvals' },
  },
  { path: '**', redirectTo: 'brief' },
];
