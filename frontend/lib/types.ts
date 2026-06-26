export interface Product {
  id: string;
  user_id: string;
  name: string;
  description: string;
  category: string;
  substances: string[];
  markets: string[];
  compliance_streams: string[];
  has_battery: boolean;
  battery_type: string;
  battery_capacity_wh: number;
  has_radio: boolean;
  intended_use: string;
  packaging: string[];
  created_at: string;
  open_alerts: number;
}

export interface ClassifyResult {
  name: string;
  category: string;
  substances: string[];
  has_battery: boolean;
  battery_type: string;
  battery_capacity_wh: number;
  has_radio: boolean;
  intended_use: string;
  markets: string[];
  compliance_streams: string[];
  reasoning: string;
}

export interface Citation {
  line_no: number;
  text: string;
  reference: string;
  source_url: string;
  cause: string;
  effect: string;
  dates: string[];
}

export interface Alert {
  id: string;
  product_id: string;
  regulation_label: string;
  regulation_title: string;
  alert_message: string;
  requirement: string;
  gap: string;
  recommended_action: string;
  severity: string;
  deadline: string | null;
  source_url: string;
  confidence: number;
  delivery_status: string;
  citations: Citation[];
  product_impact: string;
  business_impact: string;
  key_dates: string[];
  is_read: boolean;
  created_at: string;
  product_name: string | null;
  company_name: string | null;
}

export interface ProductAnalytics {
  product: {
    id: string;
    name: string;
    category: string;
    description: string;
    substances: string[];
    markets: string[];
    compliance_streams: string[];
    has_battery: boolean;
    battery_type: string;
    battery_capacity_wh: number;
    has_radio: boolean;
    intended_use: string;
  };
  company: string;
  totals: {
    open_alerts: number;
    total_alerts: number;
    labels_in_scope: number;
    labels_with_gaps: number;
  };
  orbs: { risk: number; health: number; fine_exposure_eur: number };
  by_severity: Record<string, number>;
  by_label: Record<string, number>;
  coverage: { label: string; regulation: string; source_url: string; open_gaps: number }[];
  timeline: {
    alert_id: string;
    deadline: string | null;
    days_remaining: number | null;
    label: string;
    severity: string;
    title: string;
  }[];
}

export interface Analytics {
  totals: {
    products: number;
    companies: number;
    open_alerts: number;
    clean_products: number;
    flagged_products: number;
  };
  orbs: {
    portfolio_risk: number;
    compliance_health: number;
    fine_exposure_eur: number;
    deadline_pressure: number;
  };
  by_severity: Record<string, number>;
  by_label: Record<string, number>;
  by_category: Record<string, number>;
  products_by_category: Record<string, number>;
  timeline: {
    alert_id: string;
    deadline: string | null;
    days_remaining: number | null;
    label: string;
    severity: string;
    product: string;
    company: string;
  }[];
  company_risk: {
    company: string;
    partner_id: string | null;
    products: number;
    high: number;
    medium: number;
    low: number;
    open_alerts: number;
    risk: number;
  }[];
  label_coverage: {
    label: string;
    regulation: string;
    source_url: string;
    products_in_scope: number;
    open_gaps: number;
  }[];
}

export interface DashboardMetrics {
  total_products: number;
  active_alerts: number;
  monitored_regulations: number;
}

export interface ScanResult {
  updated_labels: string[];
  products_assessed: number;
  alerts_created: number;
  message: string;
}

export interface Taxonomy {
  product_categories: Record<string, string>;
  substances: Record<string, string>;
  regulation_families: Record<string, string>;
}

export interface User {
  id: string;
  email: string;
  company_name: string;
  partner_id: string | null;
}

export interface LabelDef {
  label: string;
  regulation: string;
  source: string;
  source_url: string;
  triggers: string[];
}
