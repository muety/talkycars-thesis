/* Get average number of lanes per way within given bounding box */
/* Output: 2.4029850746268657 */
SELECT
  avg(to_number(lanes, '99'))
FROM planet_osm_line
WHERE
  way && st_transform(
    st_makeenvelope(13.40666, 52.519444, 13.447532, 52.493904, 4326),
    3857
  )
  AND highway IN ('primary', 'secondary', 'tertiary', 'residential');
