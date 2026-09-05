import {
  AlertOutline,
  BankOutline,
  BarChartOutline,
  BulbOutline,
  CalendarOutline,
  CheckOutline,
  ClockCircleOutline,
  CloseOutline,
  CopyOutline,
  DownOutline,
  EnterOutline,
  EyeOutline,
  FieldTimeOutline,
  FileTextOutline,
  FilterOutline,
  HistoryOutline,
  ReloadOutline,
  RightOutline,
  SafetyCertificateOutline,
  SearchOutline,
  SendOutline,
  TeamOutline,
  ThunderboltOutline,
  UploadOutline,
} from '@ant-design/icons-angular/icons';

/**
 * Explicit icon defs registered with ng-zorro (via NzIconModule.forRoot in
 * app.config.ts). Keep this list minimal -- add an icon here only when a
 * component actually renders it with `nz-icon`. An unregistered name renders
 * as an empty box, so anything referenced from insight-presentation.ts's
 * metric shapes must appear below.
 */
export const PULSE_ICONS = [
  // Shell: rail nav, lockup, top bar.
  ThunderboltOutline,
  BarChartOutline,
  FileTextOutline,
  SafetyCertificateOutline,
  BankOutline,
  ClockCircleOutline,
  CalendarOutline,
  DownOutline,
  ReloadOutline,
  BulbOutline,
  SearchOutline,
  EnterOutline,
  // Data quality: export.
  UploadOutline,
  // Insight card: category icons, fact panels, CTA.
  FieldTimeOutline,
  TeamOutline,
  FilterOutline,
  AlertOutline,
  RightOutline,
  HistoryOutline,
  CheckOutline,
  CloseOutline,
  EyeOutline,
  // Leadership pack.
  CopyOutline,
  SendOutline,
];
