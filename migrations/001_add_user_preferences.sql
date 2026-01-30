-- Migration: Add user preferences to profiles table

-- 1. Create ENUM types for preferences
CREATE TYPE theme_preference AS ENUM ('light', 'dark', 'system');
CREATE TYPE language_preference AS ENUM ('es', 'en');

-- 2. Add columns to profiles table with default values
ALTER TABLE public.profiles 
ADD COLUMN theme_preference theme_preference DEFAULT 'system',
ADD COLUMN language_preference language_preference DEFAULT 'es';

-- 3. Create index for language preference to optimize filtering/stats if needed
CREATE INDEX idx_profiles_language_pref ON public.profiles(language_preference);

-- 4. Comment on columns for documentation
COMMENT ON COLUMN public.profiles.theme_preference IS 'User interface theme preference (light, dark, system)';
COMMENT ON COLUMN public.profiles.language_preference IS 'User preferred language for interface and content (es, en)';
