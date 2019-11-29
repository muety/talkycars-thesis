/* Get total street length in km within given bounding box */
/* Output: 159.31409120764036 */
SELECT
  sum(st_length(way)) / 1000 AS total_length
FROM planet_osm_line
WHERE
  way && st_transform(
    st_makeenvelope(13.40666, 52.519444, 13.447532, 52.493904, 4326),
    3857
  )
  AND highway IN ('primary', 'secondary', 'tertiary', 'residential');