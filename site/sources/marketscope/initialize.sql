-- Evidence runs sources from site/ for a build and from site/.evidence/template when the
-- dev server reloads them, so the export is searched for from both.
SET file_search_path = '../data/site,../../../data/site';
