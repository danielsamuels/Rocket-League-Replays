import THREE from 'three'
import Detector from '../2d-rendering/Detector'
const OrbitControls = require('three-orbit-controls')(THREE)

let renderer
let scene
const loader = new THREE.JSONLoader()
let currentFrame = -1

if (!Detector.webgl) {
  Detector.addGetWebGLMessage({
    parent: document.querySelector('.hmp-Outer')
  })
}

function addStadium () {
  loader.load('https://media.rocketleaguereplays.com/uploads/files/stadium.json', function (geometry) {
    // create a new material
    const material = new THREE.MeshPhongMaterial({
      color: 0xaaffaa,
      shading: THREE.FlatShading
    })

    // create a mesh with models geometry and material
    const mesh = new THREE.Mesh(
      geometry,
      material
    )

    mesh.castShadow = false
    mesh.receiveShadow = true

    scene.add(mesh)
  })
}

function positionReplayObjects () {

}

function animate () {
  if (typeof scene === 'undefined') {
    return
  }

  if (typeof currentFrame !== 'undefined' && currentFrame >= 0) {
    positionReplayObjects()
  }

  requestAnimationFrame(animate)

  controls.update() // required if controls.enableDamping = true, or if controls.autoRotate = true

  render()

  console.log(camera.position)
  console.log(camera.rotation)
}

function render () {
  renderer.render(scene, camera)
}

scene = new THREE.Scene()

renderer = new THREE.WebGLRenderer()
renderer.setClearColor(0xffffff)
renderer.setPixelRatio(window.devicePixelRatio)
renderer.setSize('1248', '702', false)
renderer.shadowMap.enabled = true

const container = document.querySelector('.hmp-Outer')
container.appendChild(renderer.domElement)
renderer.domElement.style.width = '100%'

const camera = new THREE.PerspectiveCamera(50, 1248 / 702, 1, 15000)
camera.position.set(0, 0, 5000)
camera.rotation.set(1.5, 7, -5)

const controls = new OrbitControls(camera, renderer.domElement)
controls.enableDamping = true
controls.dampingFactor = 0.25

// Add lighting.
let light

light = new THREE.DirectionalLight(0xffffff)
light.castShadow = true
light.shadow.camera.left = -5000
light.shadow.camera.right = 5000
light.shadow.camera.top = 5000
light.shadow.camera.bottom = -5000
light.position.set(0, 0, 5000)
scene.add(light)

light = new THREE.DirectionalLight(0x002288)
light.position.set(1, 1, -1)
scene.add(light)

light = new THREE.DirectionalLight(0x882222)
light.position.set(-1, -1, -1)
scene.add(light)

// light = new THREE.AmbientLight(0x222222)
// scene.add(light)

addStadium()
animate()
