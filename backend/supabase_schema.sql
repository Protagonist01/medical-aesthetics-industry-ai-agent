-- =========================================================================
-- Supabase Schema for Omni-Flow Medspa AI
-- PRD v1.2 Compliant
-- =========================================================================

-- Create the costs table to track AI usage costs
CREATE TABLE IF NOT EXISTS costs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    compute_ms INTEGER NOT NULL DEFAULT 0,
    token_cost DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    compute_cost DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_cost DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =========================================================================
-- LEADS TABLE: Tracks potential clients and their qualification status
-- PRD FR-B1: Lead Parsing
-- =========================================================================
CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id TEXT NOT NULL, -- e.g., IG Handle or WhatsApp Phone
    platform TEXT NOT NULL, -- 'instagram', 'whatsapp', 'web', 'telegram'
    name TEXT,
    phone TEXT, -- PRD FR-B1: Extract Phone
    email TEXT,
    language TEXT DEFAULT 'English',
    service_interest TEXT, -- PRD FR-B1: Extract Service_Interest
    status TEXT DEFAULT 'new', -- 'new', 'qualified', 'booked', 'disqualified', 'nurture'
    qualification_data JSONB DEFAULT '{}'::jsonb, -- Stores answers to qualification Qs
    -- PRD FR-B2: Status Sync
    crm_deal_stage TEXT DEFAULT 'New Lead', -- 'New Lead', 'Conversation Started', 'Booking Proposed', 'Closed Won', 'Nurture', 'Lost'
    crm_synced_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =========================================================================
-- BOOKINGS TABLE: Tracks appointments and deposits
-- =========================================================================
CREATE TABLE IF NOT EXISTS bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id),
    service_interested TEXT,
    appointment_time TIMESTAMP WITH TIME ZONE,
    deposit_amount INTEGER DEFAULT 0,
    deposit_status TEXT DEFAULT 'pending', -- 'pending', 'paid', 'refunded'
    stripe_session_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =========================================================================
-- CONVERSATIONS TABLE: Logs message history for auditing/analytics
-- PRD FR-D2/D3: Bot Performance Tracking
-- =========================================================================
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id),
    session_id TEXT, -- Unique session identifier
    sender TEXT NOT NULL, -- 'user', 'ai', 'system', 'human'
    message TEXT NOT NULL,
    -- PRD 4.2: AI Output Payload fields
    channel TEXT DEFAULT 'web', -- 'web', 'whatsapp', 'instagram', 'telegram'
    intent TEXT, -- 'greeting', 'booking', 'inquiry', 'complaint', 'high_value', 'ambiguous', 'fallback'
    sentiment TEXT, -- 'positive', 'neutral', 'negative'
    required_action TEXT, -- 'NONE', 'OPEN_CALENDAR', 'PRIORITY_BOOKING', 'HANDOFF_LIVE_AGENT', 'SEND_PAYMENT_LINK', 'SHOW_HYBRID_OPTIONS'
    -- PRD Module C: Handoff tracking
    handoff_flag BOOLEAN DEFAULT FALSE,
    handoff_reason TEXT, -- 'ambiguity', 'high_value', 'complaint', 'medical_risk', 'fallback'
    handoff_resolved_at TIMESTAMP WITH TIME ZONE,
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =========================================================================
-- ESCALATIONS TABLE: Tracks human handoffs
-- PRD Module C: Handoff & Traffic Control
-- =========================================================================
CREATE TABLE IF NOT EXISTS escalations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id),
    conversation_id UUID REFERENCES conversations(id),
    reason TEXT NOT NULL, -- 'ambiguity', 'high_value', 'complaint', 'medical_risk', 'fallback'
    priority TEXT DEFAULT 'normal', -- 'low', 'normal', 'high', 'urgent'
    status TEXT DEFAULT 'pending', -- 'pending', 'assigned', 'resolved', 'cancelled'
    assigned_to TEXT, -- Staff member email/ID
    conversation_summary TEXT,
    resolution_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- =========================================================================
-- INDEXES
-- =========================================================================
CREATE INDEX IF NOT EXISTS idx_costs_session_id ON costs(session_id);
CREATE INDEX IF NOT EXISTS idx_leads_platform_id ON leads(platform_id);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_crm_deal_stage ON leads(crm_deal_stage);
CREATE INDEX IF NOT EXISTS idx_bookings_lead_id ON bookings(lead_id);
CREATE INDEX IF NOT EXISTS idx_conversations_lead_id ON conversations(lead_id);
CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_handoff ON conversations(handoff_flag) WHERE handoff_flag = TRUE;
CREATE INDEX IF NOT EXISTS idx_escalations_status ON escalations(status);

-- =========================================================================
-- RLS (Row Level Security)
-- =========================================================================
ALTER TABLE costs ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE escalations ENABLE ROW LEVEL SECURITY;

-- Service Role policies (backend access)
CREATE POLICY "Service role full access to costs" ON costs FOR ALL 
    USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access to leads" ON leads FOR ALL 
    USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access to bookings" ON bookings FOR ALL 
    USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access to conversations" ON conversations FOR ALL 
    USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access to escalations" ON escalations FOR ALL 
    USING (auth.role() = 'service_role');

-- =========================================================================
-- FUNCTIONS & TRIGGERS
-- =========================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Auto-update crm_deal_stage based on lead status
CREATE OR REPLACE FUNCTION sync_crm_deal_stage()
RETURNS TRIGGER AS $$
BEGIN
    -- PRD FR-B2: Status Sync
    CASE NEW.status
        WHEN 'new' THEN NEW.crm_deal_stage := 'New Lead';
        WHEN 'qualified' THEN NEW.crm_deal_stage := 'Conversation Started';
        WHEN 'booked' THEN NEW.crm_deal_stage := 'Closed Won';
        WHEN 'nurture' THEN NEW.crm_deal_stage := 'Nurture';
        WHEN 'disqualified' THEN NEW.crm_deal_stage := 'Lost';
        ELSE NEW.crm_deal_stage := NEW.crm_deal_stage;
    END CASE;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER sync_lead_to_crm
    BEFORE INSERT OR UPDATE OF status ON leads
    FOR EACH ROW
    EXECUTE FUNCTION sync_crm_deal_stage();
