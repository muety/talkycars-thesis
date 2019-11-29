/* Get area of specified bounding box im km^2 */
/* Output: 21.25240229871576 */
SELECT st_area(
    st_transform(
      st_makeenvelope(13.40666, 52.519444, 13.447532, 52.493904, 4326),
      3857
    )
  ) / (1000 * 1000) AS area;