<?xml version="1.0" encoding="UTF-8"?>
<model ref="r:11111111-1111-4111-8111-111111111111(demo.model)">
  <persistence version="9" />
  <languages>
    <use id="c72da2b9-7cce-4447-8389-f407dc1158b7" name="jetbrains.mps.lang.structure" version="9" />
  </languages>
  <imports>
    <import index="ext0" ref="r:22222222-2222-4222-8222-222222222222(other.model)" />
  </imports>
  <registry>
    <language id="c72da2b9-7cce-4447-8389-f407dc1158b7" name="jetbrains.mps.lang.structure">
      <concept id="1" name="demo.structure.Root" flags="ng" index="Croot">
        <property id="10" name="name" index="TrG5h" />
        <child id="11" name="items" index="Citems" />
      </concept>
      <concept id="2" name="demo.structure.Item" flags="ng" index="Citem">
        <property id="10" name="name" index="TrG5h" />
        <reference id="12" name="target" index="Rtarget" />
      </concept>
    </language>
  </registry>
  <node concept="Croot" id="root1">
    <property role="TrG5h" value="MyRoot" />
    <node concept="Citem" id="itemA" role="Citems">
      <property role="TrG5h" value="Alpha" />
      <ref role="Rtarget" node="itemB" resolve="Beta" />
    </node>
    <node concept="Citem" id="itemB" role="Citems">
      <property role="TrG5h" value="Beta" />
      <ref role="Rtarget" to="ext0:externalItem" resolve="External" />
    </node>
  </node>
</model>
