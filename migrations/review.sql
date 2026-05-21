-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.bite_audio_triage (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  bite_id uuid NOT NULL,
  language text NOT NULL CHECK (language = ANY (ARRAY['en'::text, 'hi'::text])),
  assignment_id uuid,
  decision text NOT NULL CHECK (decision = ANY (ARRAY['full'::text, 'partial'::text, 'skip'::text, 'escalate'::text])),
  confidence double precision CHECK (confidence >= 0::double precision AND confidence <= 1::double precision),
  reasoning text,
  segments_to_regen jsonb DEFAULT '[]'::jsonb,
  feedback_classification jsonb DEFAULT '[]'::jsonb,
  paragraph_timings jsonb DEFAULT '[]'::jsonb,
  model_used text,
  cost_input_tokens integer DEFAULT 0,
  cost_output_tokens integer DEFAULT 0,
  status text DEFAULT 'completed'::text CHECK (status = ANY (ARRAY['completed'::text, 'failed'::text, 'expired'::text])),
  admin_action text CHECK (admin_action IS NULL OR (admin_action = ANY (ARRAY['approved'::text, 'rejected'::text, 'modified'::text]))),
  admin_notes text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  segment_audio jsonb DEFAULT '[]'::jsonb,
  final_audio_url text,
  final_audio_round integer,
  CONSTRAINT bite_audio_triage_pkey PRIMARY KEY (id),
  CONSTRAINT bite_audio_triage_bite_id_fkey FOREIGN KEY (bite_id) REFERENCES public.bites(id),
  CONSTRAINT bite_audio_triage_assignment_id_fkey FOREIGN KEY (assignment_id) REFERENCES public.content_assignments(id)
);
CREATE TABLE public.bites (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  cover text,
  source_id text,
  author text,
  title text,
  audio jsonb,
  content jsonb,
  source text,
  tags jsonb,
  audio_version jsonb DEFAULT '{"en": 1, "hi": 1}'::jsonb,
  linear_identifier text,
  difficulty text,
  category text,
  author_bilingual jsonb,
  title_bilingual jsonb,
  CONSTRAINT bites_pkey PRIMARY KEY (id)
);
CREATE TABLE public.content_assignments (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  reviewer_id uuid,
  content_type text,
  content_id uuid,
  status text,
  assigned_by uuid,
  assigned_at timestamp with time zone DEFAULT now(),
  completed_at timestamp with time zone,
  assigned_languages jsonb,
  iteration_count integer DEFAULT 0,
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT content_assignments_pkey PRIMARY KEY (id),
  CONSTRAINT content_assignments_reviewer_id_fkey FOREIGN KEY (reviewer_id) REFERENCES public.profiles(id),
  CONSTRAINT content_assignments_assigned_by_fkey FOREIGN KEY (assigned_by) REFERENCES public.profiles(id)
);
CREATE TABLE public.fix_lab_job_items (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  job_id uuid,
  bite_id uuid NOT NULL,
  assignment_id uuid,
  language text NOT NULL,
  status text NOT NULL DEFAULT 'pending'::text,
  error text,
  result jsonb,
  created_at timestamp with time zone DEFAULT now(),
  from_version integer,
  new_version integer,
  new_round integer,
  uploaded_url text,
  uploaded_at timestamp with time zone,
  storage_verified boolean,
  assignment_fixed boolean,
  assignment_fix_error text,
  triage_id uuid,
  CONSTRAINT fix_lab_job_items_pkey PRIMARY KEY (id),
  CONSTRAINT fix_lab_job_items_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.fix_lab_jobs(id),
  CONSTRAINT fix_lab_job_items_triage_id_fkey FOREIGN KEY (triage_id) REFERENCES public.bite_audio_triage(id)
);
CREATE TABLE public.fix_lab_jobs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  status text NOT NULL DEFAULT 'running'::text,
  total integer DEFAULT 0,
  completed integer DEFAULT 0,
  failed integer DEFAULT 0,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT fix_lab_jobs_pkey PRIMARY KEY (id)
);
CREATE TABLE public.journeys (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  cover text,
  source_id text,
  author text,
  title text,
  content jsonb,
  audio jsonb,
  source text,
  content_chapterwise jsonb,
  tags jsonb,
  CONSTRAINT journeys_pkey PRIMARY KEY (id)
);
CREATE TABLE public.mcp_auth_codes (
  code text NOT NULL,
  client_id text NOT NULL,
  code_challenge text NOT NULL,
  redirect_uri text NOT NULL,
  user_id uuid NOT NULL,
  access_token text NOT NULL,
  refresh_token text NOT NULL,
  scope text,
  used boolean DEFAULT false,
  expires_at timestamp with time zone NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT mcp_auth_codes_pkey PRIMARY KEY (code),
  CONSTRAINT mcp_auth_codes_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.mcp_oauth_clients (
  client_id text NOT NULL,
  redirect_uris jsonb NOT NULL DEFAULT '[]'::jsonb,
  client_name text NOT NULL DEFAULT 'MCP Client'::text,
  grant_types jsonb DEFAULT '["authorization_code", "refresh_token"]'::jsonb,
  response_types jsonb DEFAULT '["code"]'::jsonb,
  token_endpoint_auth_method text DEFAULT 'none'::text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT mcp_oauth_clients_pkey PRIMARY KEY (client_id)
);
CREATE TABLE public.profiles (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  email text,
  full_name text,
  role text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT profiles_pkey PRIMARY KEY (id)
);
CREATE TABLE public.release_notes (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  version text NOT NULL UNIQUE,
  title text NOT NULL,
  release_date date NOT NULL,
  summary text,
  is_published boolean DEFAULT false,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT release_notes_pkey PRIMARY KEY (id)
);
CREATE TABLE public.review_drafts (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  assignment_id uuid,
  reviewer_id uuid,
  rating integer,
  feedback_items jsonb,
  verification_status text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT review_drafts_pkey PRIMARY KEY (id),
  CONSTRAINT review_drafts_assignment_id_fkey FOREIGN KEY (assignment_id) REFERENCES public.content_assignments(id),
  CONSTRAINT review_drafts_reviewer_id_fkey FOREIGN KEY (reviewer_id) REFERENCES public.profiles(id)
);
CREATE TABLE public.reviews (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  assignment_id uuid,
  reviewer_id uuid,
  rating integer,
  is_verified boolean DEFAULT false,
  created_at timestamp with time zone DEFAULT now(),
  feedback_details jsonb,
  CONSTRAINT reviews_pkey PRIMARY KEY (id),
  CONSTRAINT reviews_assignment_id_fkey FOREIGN KEY (assignment_id) REFERENCES public.content_assignments(id),
  CONSTRAINT reviews_reviewer_id_fkey FOREIGN KEY (reviewer_id) REFERENCES public.profiles(id)
);
CREATE TABLE public.summaries (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  cover text,
  source_id text,
  author text,
  title text,
  feedback jsonb,
  content jsonb,
  audio jsonb,
  source text,
  tags jsonb,
  linear_identifier text,
  CONSTRAINT summaries_pkey PRIMARY KEY (id)
);