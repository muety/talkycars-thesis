// ray_intersect.cu
// Source: https://gamedev.stackexchange.com/a/103714/130059
__device__ float rayBoxIntersect ( float3 rpos, float3 rdir, float3 vmin, float3 vmax )
{
   float t[10];
   t[1] = (vmin.x - rpos.x)/rdir.x;
   t[2] = (vmax.x - rpos.x)/rdir.x;
   t[3] = (vmin.y - rpos.y)/rdir.y;
   t[4] = (vmax.y - rpos.y)/rdir.y;
   t[5] = (vmin.z - rpos.z)/rdir.z;
   t[6] = (vmax.z - rpos.z)/rdir.z;
   t[7] = fmax(fmax(fmin(t[1], t[2]), fmin(t[3], t[4])), fmin(t[5], t[6]));
   t[8] = fmin(fmin(fmax(t[1], t[2]), fmax(t[3], t[4])), fmax(t[5], t[6]));
   t[9] = (t[8] < 0 || t[7] > t[8]) ? NOHIT : t[7];
   return t[9];
}