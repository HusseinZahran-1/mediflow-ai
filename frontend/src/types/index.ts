export type Role = 'ADMIN' | 'RECEPTIONIST' | 'TRIAGE_NURSE' | 'NURSE' | 'DOCTOR' | 'LAB_TECHNICIAN' | 'RADIOLOGY_TECHNICIAN' | 'PHARMACIST' | 'DISPLAY'
export type Priority = 'CRITICAL' | 'URGENT' | 'NORMAL'

export interface User { id: number; email: string; full_name: string; role: Role; is_active: boolean }
export interface AuthResponse { access_token: string; refresh_token: string; token_type: string; expires_in: number; user: User }
export interface Patient {
  id: number; medical_record_number: string; full_name: string; phone_number?: string; gender: string; date_of_birth?: string;
  age?: number; nationality?: string; identity_type: string; identity_number: string; is_military: boolean; military_number?: string;
  blood_type?: string; created_at: string;
}
export interface Department { id: number; name: string; code: string; ticket_prefix: string; description?: string; is_active: boolean }
export interface Visit {
  id: number; patient_id: number; department_id: number; ticket_code: string; ticket_sequence: number; arrival_time: string;
  status: string; visit_type: string; arrival_method: string; final_priority?: Priority; human_priority?: Priority; ai_priority?: Priority;
  assigned_room_id?: number; assigned_doctor_id?: number;
}
export interface QueueItem {
  visit_id: number; ticket_code: string; patient_name: string; department_id: number; department: string; priority: Priority; status: string;
  arrival_time: string; wait_minutes: number; room?: string;
}
export interface Metrics {
  patients_today: number; waiting: number; critical: number; urgent: number; normal: number; completed: number;
  average_wait_minutes: number; longest_wait_minutes: number; by_department: Array<{ department: string; patients: number }>;
}
export interface Triage {
  id: number; visit_id: number; chief_complaint: string; human_priority: Priority; ai_priority?: Priority; ai_confidence?: number;
  final_priority?: Priority; symptoms?: string; symptom_start_time?: string; pain_level?: number; oxygen_saturation?: number; heart_rate?: number;
  systolic_bp?: number; diastolic_bp?: number; temperature?: number; respiratory_rate?: number; blood_glucose?: number; weight?: number;
  height?: number; consciousness_level?: string; severe_bleeding?: boolean; difficulty_breathing?: boolean; chest_pain?: boolean;
  seizure?: boolean; loss_of_consciousness?: boolean; severe_allergy?: boolean; pregnancy?: boolean; recent_surgery?: boolean;
  chronic_diseases?: string; medications?: string; nurse_notes?: string; disagreement_reason?: string; finalized_at?: string;
}

export interface CompletedVisitItem {
  visit_id: number; patient_id: number; medical_record_number: string; patient_name: string; phone_number?: string; gender: string; age?: number; identity_number: string;
  ticket_code: string; department_id: number; department_name: string; assigned_doctor_id?: number; doctor_name?: string; priority?: Priority; status: string;
  arrival_time: string; started_at?: string; completed_at?: string; duration_minutes?: number; diagnosis?: string; clinical_notes?: string; treatment_plan?: string;
}
export interface CompletedVisitPage { items: CompletedVisitItem[]; total: number; page: number; page_size: number }
