export interface User {
  id: string;
  email: string;
  full_name: string;
  phone?: string;
  role: 'SUPER_ADMIN' | 'BRANCH_ADMIN' | 'CUSTOMER';
  is_active: boolean;
  branch_ids: string[];
}

export interface Branch {
  id: string;
  code: string;
  name: string;
  address_line1: string;
  postcode: string;
  city: string;
  latitude: number;
  longitude: number;
  phone?: string;
  delivery_enabled: boolean;
  collection_enabled: boolean;
  ordering_enabled: boolean;
  delivery_radius_miles: number;
  opening_hours?: any;
  is_active: boolean;
}

export interface BranchStats {
  branch_id: string;
  code: string;
  name: string;
  total_orders: number;
  completed_orders: number;
  cancelled_orders: number;
  pending_orders: number;
}

export interface BranchAdmin {
  id: string;
  name: string;
  email: string;
  is_active: boolean;
  branch_id: string;
  branch_name: string;
  created_at?: string;
}

export interface ProductModifier {
  id: string;
  name: string;
  price: number;
  is_required: boolean;
  is_active: boolean;
}

export interface ProductChoiceOption {
  id: string;
  group_id?: string;
  name: string;
  price_delta: number;
  is_active: boolean;
  display_order?: number;
}

export interface ProductChoiceGroup {
  id: string;
  product_id?: string;
  name: string;
  min_selections: number;
  max_selections: number;
  is_required: boolean;
  display_order?: number;
  options: ProductChoiceOption[];
}

export interface SelectedChoice {
  group_id: string;
  group_name: string;
  option_id: string;
  option_name: string;
  price_delta: number;
}

export interface Product {
  id: string;
  category_id: string;
  name: string;
  sku: string;
  short_description?: string;
  full_description?: string;
  description?: string;
  allergens?: string;
  ingredients?: string[];
  image_url?: string;
  images?: string[];
  base_price: number;
  compare_at_price?: number;
  rating: number;
  reviews_count: number;
  is_bestseller: boolean;
  has_tax: boolean;
  has_service_charge: boolean;
  vat_category: string;
  is_active: boolean;
  is_available?: boolean;
  is_out_of_stock?: boolean;
  modifiers: ProductModifier[];
  choice_groups?: ProductChoiceGroup[];
  stock_quantity?: number;
}

export interface Category {
  id: string;
  name: string;
  slug: string;
  icon?: string;
  display_order: number;
}

export interface CartItem {
  product: Product;
  quantity: number;
  selectedModifiers: ProductModifier[];
  selectedChoices?: SelectedChoice[];
  removedIngredients?: string[];
  lineTotal: number;
}

export interface OrderItem {
  id: string;
  product_id: string;
  product_name: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  selected_modifiers?: { name: string; price?: number; group_name?: string; option_name?: string; is_choice?: boolean }[];
  selected_choices?: SelectedChoice[];
  image_url?: string;
}

export interface OrderStatusHistory {
  id: string;
  from_status?: string;
  to_status: string;
  notes?: string;
  created_at: string;
}

export interface Order {
  id: string;
  order_number: string;
  customer_name: string;
  customer_email: string;
  customer_phone: string;
  branch_id: string;
  order_type: 'DELIVERY' | 'COLLECTION';
  status: string;
  delivery_address?: any;
  collection_slot_time?: string;
  delivery_instructions?: string;
  subtotal: number;
  delivery_fee: number;
  service_fee: number;
  discount_amount: number;
  vat_amount: number;
  total_amount: number;
  payment_method: string;
  payment_status: string;
  payment_transaction_id?: string;
  coupon_code?: string;
  points_earned: number;
  points_redeemed: number;
  created_at: string;
  items: OrderItem[];
  status_history: OrderStatusHistory[];
}

export interface Coupon {
  id: string;
  code: string;
  name: string;
  coupon_type: string;
  discount_value: number;
  min_order_value: number;
  usage_limit: number;
  used_count: number;
}

export interface LoyaltyReward {
  id: string;
  title: string;
  description?: string;
  points_required: number;
  reward_type: string;
  discount_value?: number;
  product_id?: string;
}

export interface LoyaltyTransaction {
  id: string;
  points: number;
  transaction_type: string;
  description?: string;
  order_id?: string;
  campaign_id?: string;
  resulting_balance?: number;
  admin_email?: string;
  created_at: string;
}

export interface LoyaltyMilestone {
  milestone_id: string;
  milestone_name: string;
  points_required: number;
  points_needed: number;
  is_unlocked: boolean;
  progress_percent: number;
  reward_value: number;
  description?: string;
}

export interface LoyaltyCampaign {
  id: string;
  name: string;
  campaign_type: string;
  multiplier: number;
  bonus_points: number;
  start_date?: string;
  end_date?: string;
  is_active: boolean;
  eligible_products?: string[];
  excluded_products?: string[];
  eligible_categories?: string[];
  excluded_categories?: string[];
  created_at?: string;
  updated_at?: string;
}

export interface LoyaltyOverview {
  available_points: number;
  lifetime_points: number;
  total_redeemed_points: number;
  total_reversed_points: number;
  reward_value: number;
  is_redemption_available: boolean;
  min_redemption_points: number;
  points_needed_for_redemption: number;
  max_redeemable_reward: number;
  redeemable_increments: number[];
  active_campaign?: {
    id: string;
    name: string;
    campaign_type: string;
    multiplier: number;
    bonus_points: number;
  };
  primary_milestone: LoyaltyMilestone;
  transactions: LoyaltyTransaction[];
}

export interface LoyaltyProgramConfig {
  id: string;
  is_enabled: boolean;
  earning_rate_pence_per_point: number;
  points_per_pound_reward: number;
  min_redemption_points: number;
  redemption_increment_points: number;
  updated_at?: string;
  updated_by?: string;
}

export interface LoyaltyMemberSummary {
  user_id: string;
  full_name: string;
  email: string;
  phone?: string;
  role?: string;
  available_points: number;
  lifetime_points: number;
  total_redeemed: number;
  total_reversed: number;
  reward_value: number;
  is_redemption_eligible: boolean;
  created_at: string;
}

export interface LoyaltyAnalytics {
  total_members: number;
  total_active_points: number;
  total_points_issued: number;
  total_points_redeemed: number;
  total_points_reversed: number;
  total_reward_value_issued: number;
  total_reward_value_redeemed: number;
  total_outstanding_liability_pounds: number;
  active_campaigns_count: number;
  is_programme_active: boolean;
}
