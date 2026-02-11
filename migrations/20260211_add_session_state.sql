-- Add current_state column to chat_sessions to persist AI context
ALTER TABLE public.chat_sessions 
ADD COLUMN IF NOT EXISTS current_state JSONB DEFAULT '{}'::jsonb;

COMMENT ON COLUMN public.chat_sessions.current_state IS 'Stores the full SessionStateSchema (slots, phase, iteration) for AI continuity.';
