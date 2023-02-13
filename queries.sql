-- SQL-scripts


-- 1) Топ 5 найпопулярніших статей (ті що мають найбільшу кількість посилань на себе)
SELECT
	COUNT(l1.parent_id) AS count_linkes_on_me,
	p1.page_id AS page_id,
	p1.page_title AS page_title
FROM links l1
	LEFT JOIN pages p1 ON p1.page_id = l1.child_id
WHERE p1.page_status = 2
GROUP BY p1.page_id, p1.page_title
ORDER BY count_linkes_on_me DESC, page_title ASC
LIMIT 5;


-- 2) Топ 5 статей з найбільшою кількістю посилань на інші статті
SELECT
	COUNT(l1.child_id) AS count_linkes_on_other,
	p1.page_id AS page_id,
	p1.page_title AS page_title
FROM links l1
	LEFT JOIN pages p1 ON p1.page_id = l1.parent_id
WHERE p1.page_status = 2
GROUP BY p1.page_id, p1.page_title
ORDER BY count_linkes_on_other DESC, page_title ASC
LIMIT 5;


-- 3) Для заданної статті знайти середню кількість нащадків другого рівня
WITH tmp_tbl_1 AS (
    SELECT
 		p0.page_id AS p0_id,
 		p1.page_id AS p1_id,
 		COUNT(p2.page_id) AS p2_count
 	FROM pages p0
 		INNER JOIN links l1 ON l1.parent_id = p0.page_id
 		INNER JOIN pages p1 ON p1.page_id = l1.child_id AND p1.page_status = 2
 		INNER JOIN links l2 ON l2.parent_id = p1.page_id
 		INNER JOIN pages p2 ON p2.page_id = l2.child_id AND p2.page_status = 2
 	WHERE p0.page_title = 'Дружба' AND p0.page_status = 2
 	GROUP BY p0.page_id, p1.page_id
)
SELECT AVG(tmp_tbl_1.p2_count) AS avg_count_childs_N2
FROM tmp_tbl_1
GROUP BY tmp_tbl_1.p0_id;

/*
4) (На додаткові бали) Запит, що має параметр - N, повертає до п’яти маршрутів переходу довжиною N.
Сторінки в шляху не мають повторюватись.

NOTE:
Task 4. was implemented on the basis of four functions:
   -get_next_generation_chains()
   -get_routes_with_n_depth_by_start_page_limit_count()
   -get_all_valid_pages_order_random()
   -get_routes_with_n_depth_limit_count() - main function
These functions need to be created.
To get the result, you need to call main function get_routes_with_n_depth_limit_count()
*/

--function 1, get_next_generation_chains()
CREATE OR REPLACE FUNCTION public.get_next_generation_chains(
	p_start_page_id bigint,
	p_end_page_id bigint,
	p_route_arr character varying[],
	p_route_depth integer)
    RETURNS TABLE(ch_start_page_id bigint, ch_end_page_id bigint, ch_end_page_title character varying, ch_route_arr character varying[], ch_route_depth integer)
    LANGUAGE 'plpgsql'
    COST 100
    VOLATILE PARALLEL UNSAFE
    ROWS 1000

AS $BODY$
declare
    var_r record;
begin
	for var_r in(
            select
				p.page_id as child_page_id,
				p.page_title as child_page_title
            from links l
				inner join pages p on p.page_id = l.child_id
	     	where l.parent_id = p_end_page_id
				and p.page_status = 2
				and not (p.page_title = any(p_route_arr))
        ) loop
		ch_start_page_id := p_start_page_id;
		ch_end_page_id := var_r.child_page_id;
		ch_end_page_title := var_r.child_page_title;
		ch_route_arr := array_append(p_route_arr, var_r.child_page_title);
		ch_route_depth := p_route_depth + 1;
           return next;
	end loop;
end;
$BODY$;

--function 2, get_routes_with_n_depth_by_start_page_limit_count()
CREATE OR REPLACE FUNCTION public.get_routes_with_n_depth_by_start_page_limit_count(
	in_start_page_id bigint,
	in_route_depth integer,
	in_route_count_limit integer)
    RETURNS TABLE(start_page_id bigint, end_page_id bigint, route_arr character varying[], route_depth integer)
    LANGUAGE 'plpgsql'
    COST 100
    VOLATILE PARALLEL UNSAFE
    ROWS 1000

AS $BODY$

declare
	cur_generation integer;
	cur_page_id bigint;
	cur_page_title character varying;
	cur_route_arr character varying[];
	rec record;
	rec_out record;
	n_depth_routes_count bigint := 0;

begin
	-- drop and create temporary Table: _search_route_chains_tmp
	DROP TABLE IF EXISTS _search_route_chains_tmp;
	CREATE TEMPORARY TABLE IF NOT EXISTS _search_route_chains_tmp
	(
		_start_page_id bigint NOT NULL,
		_end_page_id bigint,
		_route_arr character varying[] COLLATE pg_catalog."default" NOT NULL,
		_route_depth integer NOT NULL
	);

	--build and insert start_page_title by id
	cur_generation := 0;
	cur_page_id := in_start_page_id;
	cur_page_title := (SELECT page_title FROM pages WHERE page_id = cur_page_id);
	cur_route_arr := array_append(cur_route_arr, cur_page_title);
	INSERT INTO _search_route_chains_tmp(_start_page_id, _end_page_id, _route_arr, _route_depth)
	VALUES(cur_page_id, cur_page_id, cur_route_arr, cur_generation);

	--loop 1 with increment generation
	while cur_generation < in_route_depth loop
		--increment generation
		cur_generation := cur_generation + 1;

		--loop 2. get all routes with cur_generation and do iteretions
		for rec in select _start_page_id, _end_page_id, _route_arr, _route_depth
					from _search_route_chains_tmp
					where _start_page_id = in_start_page_id and _route_depth = cur_generation - 1
					order by _route_arr
					limit 1000000

		loop
			--if cur_generation < 4 -> get childs no limits
			if cur_generation < 3 then
				INSERT INTO _search_route_chains_tmp(_start_page_id, _end_page_id, _route_arr, _route_depth)
				SELECT ch_start_page_id, ch_end_page_id, ch_route_arr, ch_route_depth
				FROM get_next_generation_chains(rec._start_page_id, rec._end_page_id, rec._route_arr, rec._route_depth);
			--if cur_generation >= 4 -> get one random child from paren page
			else
				INSERT INTO _search_route_chains_tmp(_start_page_id, _end_page_id, _route_arr, _route_depth)
				SELECT ch_start_page_id, ch_end_page_id, ch_route_arr, ch_route_depth
				FROM get_next_generation_chains(rec._start_page_id, rec._end_page_id, rec._route_arr, rec._route_depth)
				ORDER BY random()
				LIMIT 1;
			end if;

			--check how much routes we have in tmp table
			n_depth_routes_count := (SELECT COUNT(_start_page_id)
									 FROM _search_route_chains_tmp
									 WHERE _route_depth = in_route_depth);

			--if we have routes in tmp table >= in_route_count_limit -> return it and exit loop
			if n_depth_routes_count >= in_route_count_limit then
				--insert data into return table from tmp table
				for rec_out in(SELECT _start_page_id, _end_page_id, _route_arr, _route_depth
							   FROM _search_route_chains_tmp
							   WHERE _route_depth = in_route_depth
							   ORDER BY _end_page_id
							   LIMIT in_route_count_limit
					) loop
					--add rec into return table
					start_page_id := rec_out._start_page_id;
					end_page_id := rec_out._end_page_id;
					route_arr := rec_out._route_arr;
					route_depth := rec_out._route_depth;
					return next;
				end loop;

				exit;

			end if;
		end loop;
	end loop;

	--drop tmp table
	DROP TABLE IF EXISTS _search_route_chains_tmp;

end;
$BODY$;

--function 3, get_all_valid_pages_order_random()
CREATE OR REPLACE FUNCTION public.get_all_valid_pages_order_random(
	)
    RETURNS TABLE(page_id bigint, page_title character varying, count_childs integer)
    LANGUAGE 'plpgsql'
    COST 100
    VOLATILE PARALLEL UNSAFE
    ROWS 1000

AS $BODY$
declare
    var_r record;
begin
	for var_r in(
					select
						p1.page_id as page_id,
						p1.page_title as page_title,
						count(l1.child_id) as count_childs
					from links l1
						left join pages p1 on p1.page_id = l1.parent_id
					where p1.page_status = 2
					group by p1.page_id, p1.page_title
					order by random()
				) loop
		page_id := var_r.page_id;
		page_title := var_r.page_title;
		count_childs := var_r.count_childs;
        return next;
	end loop;
end;
$BODY$;

--function 4 (main), get_routes_with_n_depth_limit_count()
CREATE OR REPLACE FUNCTION public.get_routes_with_n_depth_limit_count(
	in_route_depth integer,
	in_route_count_limit integer)
    RETURNS TABLE(out_start_page_id bigint,
                  out_end_page_id bigint,
                  out_route_arr character varying[],
                  out_route_depth integer)
    LANGUAGE 'plpgsql'
    COST 100
    VOLATILE PARALLEL UNSAFE
    ROWS 1000

AS $BODY$

declare
    cur_start_page_rec record;
	cur_route record;
	cur_routes_count integer := 0;

begin
	--get all valid pages ordered by random()
	for cur_start_page_rec in(
		select page_id from get_all_valid_pages_order_random()
	)
	loop
		--get routes (count limited by in_param) with defined n_depth by start_page
		for cur_route in(
			select * from get_routes_with_n_depth_by_start_page_limit_count(cur_start_page_rec.page_id,
																			in_route_depth,
																			in_route_count_limit)
		)
		loop

			--add rec into return table
			out_start_page_id := cur_route.start_page_id;
			out_end_page_id := cur_route.end_page_id;
			out_route_arr := cur_route.route_arr;
			out_route_depth := cur_route.route_depth;
			return next;

			--increment routes counter
			cur_routes_count := cur_routes_count + 1;

		end loop;

		--check routes counter
		if cur_routes_count = in_route_count_limit then
			exit;
		end if;

	end loop;
end;
$BODY$;

/*
Example, call main function get_routes_with_n_depth_limit_count()
where first parameter(int) - N (the depth of routes), second parameter(int) - get rows limit
*/
SELECT * FROM get_routes_with_n_depth_limit_count(5, 5);
