/*
 * Berlin OSM data: http://download.geofabrik.de/europe/germany/berlin.html
 * osm2postgis: https://gis.stackexchange.com/questions/12858/retrieve-speed-and-number-of-lanes-in-google-maps-api-osm-data-or-any-other-str/57766#57766
 * Berlin Mitte center: 52.519444, 13.40666
 */


/* Get different road types */
SELECT
  distinct(highway)
FROM
  planet_osm_line;


/* Get different surface types */
SELECT
  distinct(surface)
FROM
  planet_osm_line;


/* Get area of specified bounding box im km² */
/* Output: 21.25240229871576 */
SELECT
  st_area(
    st_transform(
      st_makeenvelope(
        13.40666, 52.519444, 13.447532, 52.493904,
        4326
      ),
      3857
    )
  ) / (1000 * 1000) AS area;


/* Get total street length in km within given bounding box */
/* Output: 159.31409120764036 */
SELECT
  sum(
    st_length(way)
  ) / 1000 AS total_length
FROM
  planet_osm_line
WHERE
  way && st_transform(
    st_makeenvelope(
      13.40666, 52.519444, 13.447532, 52.493904,
      4326
    ),
    3857
  )
  AND highway IN (
    'primary', 'secondary', 'tertiary',
    'residential'
  );


/* Get average number of lanes per way within given bounding box */
/* Output: 2.4029850746268657 */
SELECT
  avg(
    to_number(lanes, '99')
  )
FROM
  planet_osm_line
WHERE
  way && st_transform(
    st_makeenvelope(
      13.40666, 52.519444, 13.447532, 52.493904,
      4326
    ),
    3857
  )
  AND highway IN (
    'primary', 'secondary', 'tertiary',
    'residential'
  );
